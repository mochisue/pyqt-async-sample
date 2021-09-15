import sys
import traceback

from progress import HIDE_CURSOR, SHOW_CURSOR
from progress.bar import Bar
from PyQt6.QtCore import (Q_ARG, QMetaObject, QMutex, QMutexLocker, QObject,
                          QRunnable, Qt, QThreadPool, pyqtSignal, pyqtSlot)
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QMainWindow,
                             QMessageBox, QPlainTextEdit, QPushButton,
                             QVBoxLayout, QWidget)


class WorkerSignals(QObject):
    finish = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)


class Worker(QRunnable):
    def __init__(self, fn_run, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn_run = fn_run
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.mutex = QMutex()
        self.is_stop = False

    @pyqtSlot()
    def run(self):
        try:
            with QMutexLocker(self.mutex):
                self.is_stop = False
            result = self.fn_run(self, *self.args, **self.kwargs)
        except:
            self.signals.error.emit(traceback.format_exc())
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finish.emit()

    def stop(self):
        with QMutexLocker(self.mutex):
            self.is_stop = True


class CustomPlainTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super(CustomPlainTextEdit, self).__init__(parent=parent)
        self.is_progress_bar = False

    def write(self, message):
        # Support for "progress" module
        message = message.strip()
        if message == SHOW_CURSOR:
            self.is_progress_bar = False
            return
        if message:
            if self.is_progress_bar:
                QMetaObject.invokeMethod(self, "replace_last_line", Qt.ConnectionType.QueuedConnection, Q_ARG(str, message))
            else:
                QMetaObject.invokeMethod(self, "appendPlainText", Qt.ConnectionType.QueuedConnection, Q_ARG(str, message))
        if message == HIDE_CURSOR:
            self.is_progress_bar = True
            return

    @pyqtSlot(str)
    def replace_last_line(self, text):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self.insertPlainText(text)

    def flush(self):
        pass


class MainWindow(QMainWindow):
    # Qt signal when asynchronous processing is interrupted
    stop_worker = pyqtSignal()

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        # Configure GUI components
        self.set_gui()
        # Required for asynchronous processing
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(1)

    def set_gui(self):
        # Asynchronous processing
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_button_clicked)
        # Asynchronous termination
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_button_pushed)
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        # Display area for standard output during asynchronous processing
        self.text_area = CustomPlainTextEdit()
        self.text_area.setReadOnly(True)
        # Place the Qt Widget
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(self.start_button)
        h_layout.addWidget(self.stop_button)
        main_layout.addLayout(h_layout)
        main_layout.addWidget(self.text_area)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.resize(600, 300)

    def closeEvent(self, event):
        # Do not close the application while asynchronous processing is running.
        if self.thread_pool.activeThreadCount() > 0:
            QMessageBox.information(None, "", "Processing is in progress", QMessageBox.StandardButton.Ok)
            event.ignore()
        else:
            event.accept()

    def start_button_clicked(self):
        # Implement the thread
        if self.thread_pool.activeThreadCount() < self.thread_pool.maxThreadCount():
            # Change the output destination to text_are
            self.old_stdout = sys.stdout
            sys.stdout = self.text_area
            print("Start asynchronous processing")
            self.worker = Worker(self.run_thread, "sample args", sample_kwargs1=1, sample_kwargs2="option")
            self.stop_worker.connect(self.worker.stop)
            self.worker.signals.finish.connect(self.finish_thread)
            self.worker.signals.error.connect(self.error_thread)
            self.worker.signals.result.connect(self.result_thread)
            self.thread_pool.start(self.worker)

    def stop_button_pushed(self):
        if self.thread_pool.activeThreadCount() > 0:
            print("Request to suspend processing")
            self.stop_worker.emit()

    def run_thread(self, worker_object, *args, **kwargs):
        # The number and type of arguments can be rewritten.
        # However, the first argument should be fixed to "worker_object".
        # This is necessary to describe the abort process.
        print("Start the main process")
        print(f"args: {args}")
        print(f"kwargs: {kwargs}")
        import time

        loop_count = 10
        suffix = "%(index)d/%(max)d [%(elapsed_td)s>%(eta_td)s]"
        for _ in Bar("Progress", suffix=suffix, empty_fill=chr(0xFFEE), fill=chr(0xFFED), file=sys.stdout, check_tty=False).iter(range(loop_count)):
            if worker_object.is_stop:  # When you can safely interrupt the process, please describe it like this
                return "Interruption"
            time.sleep(0.5)

        return "Successful completion"

    def error_thread(self, message):
        print("Outputs error logs that occur in asynchronous processing")
        print(message)

    def result_thread(self, message):
        print(f"Return value:{message}")

    def finish_thread(self):
        print("Asynchronous processing is complete")
        # Restore the standard output destination
        sys.stdout = self.old_stdout
        self.thread_pool.waitForDone()


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
