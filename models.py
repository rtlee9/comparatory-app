from app import db
from sqlalchemy.dialects.postgresql import JSON


class Result(db.Model):
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String())
    match = db.Column(JSON)
    result = db.Column(JSON)

    def __init__(self, query, match, result):
        self.query = query
        self.match = match
        self.result = result

    def __repr__(self):
        return '<id {}: {}>'.format(self.id, self.query)
