from jwt import encode, decode
import datetime

def makeAccountJwt(account: str) -> str:
    secret = "this_is_the_secret"
    payload = {
        "account": account,
        "exp": datetime.datetime.now() + datetime.timedelta(days=30),
    }
    return encode(payload, secret, algorithm='HS256')


def resolveAccountJwt(token: str) -> dict:
    secret = "this_is_the_secret"
    return decode(token, secret, algorithms='HS256')


if __name__ == '__main__':
    token = makeAccountJwt("gsycl2004")
    print(token)
