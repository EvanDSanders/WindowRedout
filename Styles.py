
BUTTON_STYLE = """
            QPushButton {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                border: 1px solid #777;
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: rgba(120, 120, 120, 220);
                border: 1px solid #bbb;
            }
            QPushButton:pressed {
                background-color: rgba(120, 120, 200, 220);
                border: 1px solid #3399ff;
            }
        """

PROGRESS_STYLE = """
            QProgressBar {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                border: 1px solid #777;
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3399ff;
                border-radius: 3px;
            }
        """

SUCCESS_STYLE = """
            QLabel {
                background-color: rgba(50, 150, 50, 200);
                color: white;
                border: 1px solid #5f5;
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
            }
        """

ERROR_STYLE = """
            QPushButton {
                background-color: rgba(150, 50, 50, 200);
                color: white;
                border: 1px solid #f55;
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: rgba(180, 80, 80, 220);
                border: 1px solid #f77;
            }
            QPushButton:pressed {
                background-color: rgba(200, 120, 120, 220);
                border: 1px solid #f99;
            }
        """

WINDOW_STYLE = """
            QWidget {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                border: 1px solid #777;
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
            }
        """


CLEAR_STYLE = """
            QWidget {
                background-color: rgba(0, 0, 0, 0);
                color: white;
                border: 0px solid #00000000;
                border-radius: 0px;
                padding: 0px;
                margin: 0px;
            }
"""