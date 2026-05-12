"""Demo API - L3 里程碑测试项目"""
from fastapi import FastAPI

app = FastAPI(title="Demo API")


@app.get("/")
def root():
    return {"message": "Demo API is running"}
