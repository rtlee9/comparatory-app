import os
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import psycopg2

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Connect to AWS RDS
try:
    conn_string = """
        host='***REMOVED***'
        dbname='comparatory' user='***REMOVED***' password='***REMOVED***'"""
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()

except psycopg2.DatabaseError:
    if conn:
        conn.rollback()


@app.route('/', methods=['GET', 'POST'])
def index():
    errors = []
    results = []
    if request.method == "POST":

        try:

            # User entry: get company name
            cname = request.form['company-name']
            print cname

            # Find next most similar
            query = """
            select
                d.id as primary_id
                ,d.company_conformed_name as primary_name
                ,d.sic_cd as primary_sic_cd
                ,d.zip as primary_zip
                ,d.city as primary_city
                ,d.state as primary_state
                ,d.state_of_incorporation as primary_state_inc
                ,d.irs_number as primary_irs_number
                ,d.filed_as_of_date as primary_filed_dt
                ,d.business_description as primary_bus_desc
                ,s.id as next_id
                ,s.company_conformed_name as next_name
                ,s.sic_cd as next_sic_cd
                ,s.zip as next_zip
                ,s.city as next_city
                ,s.state as next_state
                ,s.state_of_incorporation as next_state_inc
                ,s.irs_number as next_irs_number
                ,s.filed_as_of_date as next_filed_dt
                ,s.business_description as next_bus_desc
            from company_dets d
            inner join next_sim n
                on d.id = n.id
            inner join company_dets s
                on n.next_sim = s.id
            where replace(upper(d.COMPANY_CONFORMED_NAME), \' \', \'\') like
                \'%""" + cname.upper().replace(' ', '') + """%\'
            """

            cursor.execute(query)
            next_b = cursor.fetchall()[0]
            primary_name = next_b[1].upper().replace('&AMP;', '&')
            next_name = next_b[11].upper().replace('&AMP;', '&')
            results.append(
                'The name you entered most closely matches with: ' +
                primary_name)
            results.append(next_b[2])
            results.append(
                'The most similar company we found is: ' + next_name)
            results.append(next_b[12])
            results.append(next_b[19])

        except:
            errors.append(
                "Unable to find a company with that name -- please try again"
            )

    return render_template('index.html', errors=errors, results=results)


if __name__ == '__main__':
    app.run()
