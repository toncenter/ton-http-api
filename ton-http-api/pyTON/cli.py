import argparse
import uvicorn

from pyTON.main import app


def main():
    parser = argparse.ArgumentParser('ton-http-api')
    parser.add_argument('--host', type=str, default='localhost', help='HTTP API host')
    parser.add_argument('--port', type=int, default=8081, help='HTTP API port')

    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
