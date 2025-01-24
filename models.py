from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    publication_date = Column(String, nullable=False)  # Using String for simplicity
    body_text = Column(Text, nullable=False)
    analysis = relationship("AnalysisResult", back_populates="article", uselist=False)

class AnalysisResult(Base):
    __tablename__ = 'analysis_results'
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey('articles.id'), unique=True, nullable=False)
    company_name = Column(String)
    ceo_name = Column(String)
    summary = Column(Text)
    article = relationship("Article", back_populates="analysis")
