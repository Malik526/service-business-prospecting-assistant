"""AWS Lambda adapter for the FastAPI prospecting backend."""

from mangum import Mangum

from main import app


handler = Mangum(app)

