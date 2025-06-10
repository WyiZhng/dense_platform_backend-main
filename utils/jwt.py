from jwt import encode, decode
import datetime

<<<<<<< HEAD
=======

>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
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
