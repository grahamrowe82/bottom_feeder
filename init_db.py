from sqlalchemy import create_engine
from models import Base
import os

# Define the SQLite database filename
db_filename = 'bottom_feeder.db'

# Create the SQLite engine
engine = create_engine(f'sqlite:///{db_filename}', echo=True)

# Create all tables in the database
Base.metadata.create_all(engine)

print(f"Database '{db_filename}' and tables created successfully.")
