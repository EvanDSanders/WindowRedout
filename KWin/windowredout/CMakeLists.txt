cmake_minimum_required(VERSION 3.16)
project(kwin_effect_windowredout)

find_package(ECM REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)

find_package(Qt5 REQUIRED COMPONENTS Core Gui DBus)
find_package(KF5 REQUIRED COMPONENTS CoreAddons)
find_package(XCB REQUIRED COMPONENTS XCB)
find_package(epoxy REQUIRED)
find_package(KWinEffects REQUIRED COMPONENTS kwineffects kwinglutils)

set(CMAKE_AUTOMOC ON)
set(CMAKE_CXX_STANDARD 20)

add_library(kwin_effect_windowredout MODULE windowredout.cpp)
target_link_libraries(kwin_effect_windowredout PRIVATE
    KWinEffects::kwineffects
    KWinEffects::kwinglutils
    KF5::CoreAddons
    Qt5::Core Qt5::Gui Qt5::DBus
)

install(TARGETS kwin_effect_windowredout DESTINATION ${KDE_INSTALL_PLUGINDIR}/kwin/effects/plugins)
