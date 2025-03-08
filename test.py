import google.generativeai as genai

genai.configure(api_key="AIzaSyAy9BuATxWMgEjgedB13u1LvyNN5INWYRQ")

models = genai.list_models()

for model in models:
    print(model.name)
