from app import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(use_reloader=True, port=9000, debug=True, threaded=True)
