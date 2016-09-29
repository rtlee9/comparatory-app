import os
from flask import Flask, render_template, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
import psycopg2
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from flask_bootstrap import Bootstrap
import auth.http_basic as auth
import re


app = Flask(__name__)
Bootstrap(app)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

AWS_RDS_HOST = os.environ['AWS_RDS_HOST']
AWS_RDS_USER = os.environ['AWS_RDS_USER']
AWS_RDS_PASSWORD = os.environ['AWS_RDS_PASSWORD']
AWS_ES_ACCESS_KEY = os.environ['***REMOVED***']
AWS_ES_SECRET_KEY = os.environ['AWS_SECRET_ACCESS_KEY']


# Connect to AWS RDS
def _connect_db():
    conn_string = "host='" + AWS_RDS_HOST + \
                  "' dbname='comparatory' user='" + AWS_RDS_USER + \
                  "' password='" + AWS_RDS_PASSWORD + "'"
    conn = psycopg2.connect(conn_string)
    return conn.cursor()


# Connnect to AWS elasticsearch
def _connect_es():
    host = os.environ['ES_HOST']
    awsauth = AWS4Auth(AWS_ES_ACCESS_KEY, AWS_ES_SECRET_KEY,
                       'us-east-1', 'es')
    es = Elasticsearch(
        hosts=[host],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return es


# Opens a new elasticsearch connection if there is none yet for the
# current application context
def get_es():
    if not hasattr(g, 'es_node'):
        g.es_node = _connect_es()
    return g.es_node


# Opens a new database connection if there is none yet for the
# current application context
def get_db():
    if not hasattr(g, 'psql_db'):
        g.psql_db = _connect_db()
    return g.psql_db


# Closes the database again at the end of the request
@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'psql_db'):
        g.psql_db.close()


@app.route('/autocomplete', methods=['GET'])
def autocomplete(max_results=10):
    es = get_es()
    target_name = request.args.get('q')
    query = {"query": {"match": {
        "NAME": target_name}},
        "_source": "NAME", "size": max_results}
    resp = es.search('comparatory', 'company', query)['hits']['hits']
    assert len(resp) <= max_results

    names = [d['_source']['NAME'].title() for d in resp]
    return jsonify(matching_results=names)


@app.route('/', methods=['GET', 'POST'])
@auth.requires_auth
def index():

    es = get_es()
    cursor = get_db()

    errors = []
    match = {}
    results = {}
    if request.method == "POST":

        try:
            # User entry: get company name
            cname = request.form['company-name']

            es_query = {"query": {"match": {
                "NAME": cname}},
                "_source": "NAME", "size": 1}
            resp = es.search(
                'comparatory', 'company', es_query)['hits']['hits']
            assert len(resp) == 1
            name_match = [d['_source']['NAME'].upper() for d in resp][0]

            # Find next most similar
            query = """
            select
                d.id as primary_id
                ,d.name as primary_name
                ,d.sic_cd as primary_sic_cd
                ,d.zip as primary_zip
                ,d.city as primary_city
                ,d.state as primary_state
                ,d.state_of_incorporation as primary_state_inc
                ,d.irs_number as primary_irs_number
                ,d.filed_as_of_date as primary_filed_dt
                ,d.business_description as primary_bus_desc
                ,n.sim_score
                ,n.sim_rank
                ,s.id as next_id
                ,s.name as next_name
                ,s.sic_cd as next_sic_cd
                ,s.zip as next_zip
                ,s.city as next_city
                ,s.state as next_state
                ,s.state_of_incorporation as next_state_inc
                ,s.irs_number as next_irs_number
                ,s.filed_as_of_date as next_filed_dt
                ,s.business_description as next_bus_desc
                ,d.raw_description as primary_raw_desc
                ,s.raw_description as next_raw_desc
            from company_dets d
            inner join sims n
                on d.id = n.id
            inner join company_dets s
                on n.sim_id = s.id
            where d.NAME =
                \'""" + name_match.upper() + """\'
            """

            cursor.execute(query)

            top_sims = cursor.fetchall()
            match['name'] = str(top_sims[0][1].title())
            match['sic_cd'] = str(top_sims[0][2])
            match['business_desc'] = clean_desc(top_sims[0][22])

            for i in range(5):
                next_b = top_sims[i]
                results[i + 1] = {
                    'name': str(next_b[13].title()),
                    'sic_cd': str(next_b[14]),
                    'sim_score': str('{0:2.0f}%'.format(next_b[10] * 100)),
                    'business_desc': clean_desc(next_b[23])
                }

        except:
            errors.append(
                "Unable to find similar companies -- please try again"
            )

    return render_template(
        'index.html', errors=errors, match=match, results=results)


def clean_desc(raw):
    despaced = ' '.join(filter(lambda x: x != '', raw.split('\n')))
    despaced = ' '.join(filter(lambda x: x != '', despaced.split(' ')))
    item1 = re.compile('(\ *)ITEM 1(\.*) BUSINESS(\.*)', re.IGNORECASE)
    desc = item1.sub('', despaced).strip()
    return desc


# Sample HTTP error handling
@app.errorhandler(404)
def not_found(error):
        return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
        return render_template('500.html'), 500


if __name__ == '__main__':
    app.run()