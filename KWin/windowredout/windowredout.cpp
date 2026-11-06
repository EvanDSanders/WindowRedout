#include <kwineffects.h>
#include <kwinglutils.h>
#include <kwinoffscreeneffect.h>

#include <QDBusConnection>
#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QVector3D>
#include <QtMath>

#include <memory>
#include <unordered_map>

namespace
{
const char *FRAGMENT = R"(
uniform sampler2D sampler;
uniform vec4 modulation;
uniform vec3 gain;
varying vec2 texcoord0;

void main()
{
    vec4 tex = texture2D(sampler, texcoord0);
    tex.rgb *= gain;
    gl_FragColor = tex * modulation;
}
)";

const double CENTER_TEMP = 6500.0;
const double DAY_TEMP = 6500.0;

QVector3D rawGain(double temp)
{
    const double t = qBound(1000.0, temp, 40000.0) / 100.0;
    double r, g, b;
    r = t <= 66 ? 255 : 329.698727446 * qPow(t - 60, -0.1332047592);
    g = t <= 66 ? 99.4708025861 * qLn(t) - 161.1195681661 : 288.1221695283 * qPow(t - 60, -0.0755148492);
    if (t >= 66) {
        b = 255;
    } else if (t <= 19) {
        b = 0;
    } else {
        b = 138.5177312231 * qLn(t - 10) - 305.0447927307;
    }
    return QVector3D(qBound(0.0, r, 255.0) / 255.0, qBound(0.0, g, 255.0) / 255.0, qBound(0.0, b, 255.0) / 255.0);
}

QVector3D tempToGain(double temp)
{
    static const QVector3D white = rawGain(CENTER_TEMP);
    const QVector3D g = rawGain(temp);
    return QVector3D(g.x() / white.x(), g.y() / white.y(), g.z() / white.z());
}
}

namespace KWin
{

class WindowRedoutEffect : public OffscreenEffect
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.windowredout.Effect")

    struct Entry {
        QString cls, name, role;
        QRegularExpression regex;
        bool hasCls = false, hasName = false, hasRole = false, hasRegex = false;
        double dark = 1.0;
        double light = 0.95;
    };

    struct WindowState {
        std::unique_ptr<GLShader> shader;
        double temp = -1;
    };

public:
    WindowRedoutEffect()
    {
        connect(effects, &EffectsHandler::windowAdded, this, &WindowRedoutEffect::track);
        connect(effects, &EffectsHandler::windowDeleted, this, [this](EffectWindow *w) {
            m_windows.erase(w);
        });
        connect(effects, &EffectsHandler::windowActivated, this, [] {
            effects->addRepaintFull();
        });
        const auto windows = effects->stackingOrder();
        for (EffectWindow *w : windows) {
            track(w);
        }

        QDBusConnection bus = QDBusConnection::sessionBus();
        bus.registerObject(QStringLiteral("/WindowRedout"), this,
                           QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllInvokables);
    }

    ~WindowRedoutEffect() override
    {
        QDBusConnection::sessionBus().unregisterObject(QStringLiteral("/WindowRedout"));
        for (auto &kv : m_windows) {
            unredirect(kv.first);
        }
    }

    static bool supported()
    {
        return OffscreenEffect::supported();
    }

    bool isActive() const override
    {
        return true;
    }

    void prePaintScreen(ScreenPrePaintData &data, std::chrono::milliseconds presentTime) override
    {
        const double dt = m_lastPresent.count() ? double((presentTime - m_lastPresent).count()) : 16.0;
        m_lastPresent = presentTime;
        const double k = 1.0 - qExp(-dt / 120.0);

        bool animating = false;
        for (auto &kv : m_windows) {
            EffectWindow *w = kv.first;
            WindowState &st = kv.second;
            const double target = targetTemp(w);
            if (st.temp < 0) {
                st.temp = target;
            } else if (qAbs(target - st.temp) < 1.0) {
                st.temp = target;
            } else {
                st.temp += (target - st.temp) * k;
                animating = true;
            }
            ShaderBinder binder(st.shader.get());
            st.shader->setUniform("gain", tempToGain(st.temp));
        }
        if (animating) {
            effects->addRepaintFull();
        }
        OffscreenEffect::prePaintScreen(data, presentTime);
    }

public Q_SLOTS:
    // Replace the whole window config. JSON: [{"AppDetect": {...}, "Dark": f, "Light": f}, ...]
    void setConfig(const QString &json)
    {
        const QJsonDocument doc = QJsonDocument::fromJson(json.toUtf8());
        m_entries.clear();
        const QJsonArray arr = doc.array();
        for (const QJsonValue &v : arr) {
            const QJsonObject o = v.toObject();
            Entry e;
            e.dark = o.value(QStringLiteral("Dark")).toDouble(1.0);
            e.light = o.value(QStringLiteral("Light")).toDouble(0.95);
            const QJsonObject det = o.value(QStringLiteral("AppDetect")).toObject();
            for (auto it = det.begin(); it != det.end(); ++it) {
                const QString key = it.key().toLower();
                const QString val = it.value().toString();
                if (key == QLatin1String("class")) {
                    e.cls = val.toLower();
                    e.hasCls = true;
                } else if (key == QLatin1String("name")) {
                    e.name = val.toLower();
                    e.hasName = true;
                } else if (key == QLatin1String("role")) {
                    e.role = val.toLower();
                    e.hasRole = true;
                } else if (key == QLatin1String("regex")) {
                    e.regex = QRegularExpression(val, QRegularExpression::CaseInsensitiveOption);
                    e.hasRegex = e.regex.isValid();
                }
            }
            m_entries.append(e);
        }
        effects->addRepaintFull();
    }

    // baseTemp: time of day temperature, idleT: 0..1 idle dimming progress, allDim: mouse left the screen
    void setState(double baseTemp, double idleT, bool allDim)
    {
        m_baseTemp = baseTemp;
        m_idleT = idleT;
        m_allDim = allDim;
        effects->addRepaintFull();
    }

    // JSON of the focused window: {"class","name","role"}
    QString activeWindow()
    {
        EffectWindow *w = effects->activeWindow();
        QJsonObject o;
        if (w) {
            o[QStringLiteral("class")] = w->windowClass();
            o[QStringLiteral("name")] = w->caption();
            o[QStringLiteral("role")] = w->windowRole();
        }
        return QString::fromUtf8(QJsonDocument(o).toJson(QJsonDocument::Compact));
    }

    bool ping()
    {
        return true;
    }

private:
    void track(EffectWindow *w)
    {
        if (m_windows.count(w)) {
            return;
        }
        WindowState st;
        st.shader = ShaderManager::instance()->generateCustomShader(ShaderTrait::MapTexture | ShaderTrait::Modulate,
                                                                    QByteArray(), QByteArray(FRAGMENT));
        if (!st.shader || !st.shader->isValid()) {
            return;
        }
        redirect(w);
        setShader(w, st.shader.get());
        m_windows.emplace(w, std::move(st));
    }

    static bool matches(const Entry &e, EffectWindow *w)
    {
        if (!(e.hasCls || e.hasName || e.hasRole || e.hasRegex)) {
            return false;
        }
        const QString caption = w->caption();
        if (e.hasCls) {
            const QStringList parts = w->windowClass().toLower().split(QLatin1Char(' '), Qt::SkipEmptyParts);
            if (!parts.contains(e.cls)) {
                return false;
            }
        }
        if (e.hasName && !caption.toLower().contains(e.name)) {
            return false;
        }
        if (e.hasRole && w->windowRole().toLower() != e.role) {
            return false;
        }
        if (e.hasRegex && !e.regex.match(caption).hasMatch()) {
            return false;
        }
        return true;
    }

    double factorFor(EffectWindow *w) const
    {
        if (m_allDim) {
            return 1.1;
        }
        double dark = 1.0, light = 0.95;
        for (const Entry &e : m_entries) {
            if (matches(e, w)) {
                dark = e.dark;
                light = e.light;
                break;
            }
        }
        return w == effects->activeWindow() ? light : dark;
    }

    double targetTemp(EffectWindow *w) const
    {
        const double factor = factorFor(w);
        const double tw = CENTER_TEMP + (m_baseTemp - CENTER_TEMP) * factor;
        const double lowest = tw * 1.1;
        const double tI = DAY_TEMP + (lowest - DAY_TEMP) * m_idleT;
        return qBound(1000.0, qMin(tw, tI), 10000.0);
    }

    std::unordered_map<EffectWindow *, WindowState> m_windows;
    QList<Entry> m_entries;
    double m_baseTemp = 6500.0;
    double m_idleT = 0.0;
    bool m_allDim = false;
    std::chrono::milliseconds m_lastPresent{0};
};

KWIN_EFFECT_FACTORY_SUPPORTED(WindowRedoutEffect, "windowredout.json", return WindowRedoutEffect::supported();)

} // namespace KWin

#include "windowredout.moc"
