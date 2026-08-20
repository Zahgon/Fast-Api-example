from app.main import app


host = "0.0.0.0"
port = 8002


if __name__ == "__main__":
    app.run(host=host, port=port)
