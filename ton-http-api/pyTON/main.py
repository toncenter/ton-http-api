from xml.etree.ElementInclude import FatalIncludeError
from fastapi import FastAPI
from pyTON.api.api_v3.app import app as app_v3

app = FastAPI()
app.mount('/api/v3', app_v3, name='api_v3')
