import re

import rethinkdb as r

conn = r.connect(host="172.24.0.2", port=28015, db="test")

# r.table("products").update({'price': float(re.sub(r'\W+$', '', str(r.row['price'])).replace("'", ''))}).run(conn)

for d in r.table("products").run(conn):
    if d["price"] and d["price"] != 'None':
        price = float(re.sub(r'\W+$', '', str(d['price'])).replace("'", ''))
        print(d)
        r.table("products").get(d["id"]).update({"price": price, "currency": "CHF"}).run(conn)
