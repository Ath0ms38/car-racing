import os
import webview
from api import Api


def main():
    api = Api()
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
    window = webview.create_window(
        "NEAT Car AI Trainer",
        url=os.path.join(web_dir, "index.html"),
        js_api=api,
        width=1400,
        height=900,
        min_size=(1000, 700),
        resizable=True,
    )
    api._window = window
    webview.start(gui="qt", debug=False)


if __name__ == "__main__":
    main()
