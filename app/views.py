import requests
from collections import OrderedDict
from flask import render_template, request, jsonify, g, make_response
from flask_stormpath import login_required, user
from bokeh.embed import components

from app import app, db
from connect import get_es
from utils import comp_case
from visualizations import get_scatter
from models import Sim_search


@app.context_processor
def inject_user():
    return dict(is_authenticated=user.is_authenticated)


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

    names = [comp_case(d['_source']['NAME']) for d in resp]
    return jsonify(matching_results=names)


@app.route('/google9f59cd107587c112.html', methods=['GET'])
def google():
    return render_template('google9f59cd107587c112.html')


@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    sitemap_xml = render_template('sitemap.xml')
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/model', methods=['GET'])
@login_required
def model():
    return render_template('model.html')


@app.route('/describe', methods=['GET'])
@login_required
def describe():
    return render_template('describe.html')


@app.route('/explore', methods=['GET'])
@login_required
def graph():
    global plot
    script, div = components(plot)
    return render_template(
        'explore.html', page='explore', script=script, div=div)


@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():

    # Initialize variables to empty to prevent runtime errors
    # if no hits are found
    errors = []
    results = {}
    match = {}
    target = None
    sim_ids = []
    div = None
    script = ''

    if request.method == "POST":
        # Try getting results from SQL table, otherwise raise error
        try:
            company = request.form['company-name']
            sims = requests.post(
                app.config['API_URL'] + '/sim',
                params={"company-name": company}).json()
            match = sims['match']['data']
            target = sims['match']['key']
            results = OrderedDict(sorted(sims['results']['data'].items()))
            sim_ids = sims['results']['keys']

            # Save search to db
            db.session.add(Sim_search(user.get_id(), company))
            db.session.commit()

        except Exception as e:
            errors.append(
                "Unable to find similar companies -- please try again"
            )
            print(e)

    if target is not None:
        # Get scatter plot if results were found
        plot = get_scatter(target, sim_ids)
        script, div = components(plot)

    return render_template(
        'search.html', page='search', errors=errors, match=match,
        results=results, div=div, script=script)


@app.errorhandler(401)
def custom_401(error):
    return render_template('401.html'), 401


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


with app.app_context():
    plot = get_scatter()

if __name__ == '__main__':
    app.run()
