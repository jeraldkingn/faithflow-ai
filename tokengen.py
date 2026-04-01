import base64

with open("token.pickle", "rb") as f:
    print(base64.b64encode(f.read()).decode())


