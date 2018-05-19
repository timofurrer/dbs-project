from time import sleep
from collections import defaultdict

import maya
from flask import Flask, g, render_template, abort
from flask_socketio import SocketIO
import rethinkdb as r
import gevent
from gevent import Greenlet

app = Flask(__name__)
socketio = SocketIO(app)

# configure DB
app.config.update(dict(
    DEBUG=True,
    DB_HOST='db',
    DB_PORT=28015,
    DB_NAME='test'
))


@app.before_request
def before_request():
    try:
        g.db_conn = r.connect(
                host=app.config['DB_HOST'],
                port=app.config['DB_PORT'],
                db=app.config['DB_NAME'])
    except r.RqlDriverError:
        abort(503, "No database connection could be established.")


@app.teardown_request
def teardown_request(exception):
    try:
        g.db_conn.close()
    except AttributeError:
        pass


def watch_transactions():
    sleep(5)
    connection = r.connect(
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT'],
            db=app.config['DB_NAME'])

    # FIXME(TF): Use changes and join from rethinkdb ....
    feed = r.table("transactions").changes().run(connection)
    # feed = r.table("transactions").changes().eq_join(
            # "product_id", r.table("products")).zip().eq_join(
                    # "supplier_id", r.table("suppliers")).zip().run(connection)
    print("Started live feed for new transactions ...")
    for transaction in feed:
        full_transaction_query = r.table("transactions").filter(
                {"id": transaction["new_val"]["id"]}).eq_join(
                        "supplier_id", r.table("suppliers")).zip()
        if "product_id" in transaction["new_val"]:
            full_transaction_query = full_transaction_query.eq_join(
                    "product_id", r.table("products")).zip()

        full_transaction = full_transaction_query.run(connection).next()

        full_transaction["timestamp"] = maya.MayaDT.from_datetime(
                full_transaction["timestamp"]).rfc2822()

        socketio.emit("new_transaction", full_transaction)


@app.route('/')
def index():
    return render_template("transactions.html")


@app.route('/charts')
def charts():
    types = [x["type"] for x in r.table("transactions").pluck("type").distinct().order_by(r.asc("type")).run(g.db_conn)]

    data = defaultdict(list)
    for row in r.table("transactions").group(lambda t: t.pluck("type", "supplier_id")).order_by(r.asc("type")).count().ungroup().run(g.db_conn):
        data[row["group"]["supplier_id"]].append(row["reduction"])

    datasets = [{
        "label": k,
        "data": v} for k, v in data.items()]

    return render_template("charts.html", labels=types, datasets=datasets)


# start watching thread
Greenlet.spawn(watch_transactions)
