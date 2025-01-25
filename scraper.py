import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Article, AnalysisResult, Base
import logging
import os
import json
import re
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')

# Define the SQLite database filename
db_filename = 'bottom_feeder.db'

# Create the SQLite engine
engine = create_engine(f'sqlite:///{db_filename}')

# Ensure the database and tables are created
Base.metadata.create_all(engine)

# Create a configured "Session" class
Session = sessionmaker(bind=engine)

# Create a Session
session = Session()

# Initialize DeepSeek API
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
if not DEEPSEEK_API_KEY:
    logging.error("DeepSeek API key not found. Please set the DEEPSEEK_API_KEY environment variable.")
    exit(1)

# DeepSeek API endpoint
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

def analyze_article(body_text):
    """
    Analyze the article's body text using DeepSeek to extract company name,
    CEO name, and a summary. Returns a dictionary with the extracted information.
    """
    try:
        prompt = (
            "Extract the following information from the article below:\n"
            "- Company Name\n"
            "- CEO Name\n"
            "- Summary\n\n"
            "Article:\n"
            f"{body_text}\n\n"
            "Please provide the information in the following JSON format exactly as shown:\n"
            "{\n"
            '  "company_name": "Company Name",\n'
            '  "ceo_name": "CEO Name",\n'
            '  "summary": "Summary of the article."\n'
            "}\n"
            "Ensure that all fields are filled accurately."
        )
        
        # Prepare the request payload for DeepSeek
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",  # Replace with the correct model name
            "messages": [
                {"role": "system", "content": "You are an assistant that extracts specific information from articles."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 300
        }
        
        # Make the API request to DeepSeek
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()  # Check for HTTP errors
        
        # Extract the assistant's reply
        reply = response.json()["choices"][0]["message"]["content"].strip()
        
        # Parse the JSON response
        json_match = re.search(r'\{.*\}', reply, re.DOTALL)
        if not json_match:
            logging.error("No JSON object found in DeepSeek response.")
            return None
        
        json_str = json_match.group()
        analysis = json.loads(json_str)
        
        logging.info(f"Analysis received: {analysis}")
        
        return analysis

    except requests.exceptions.RequestException as e:
        logging.error(f"DeepSeek API request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during analysis: {e}")
        return None

def fetch_and_store_article(url):
    """
    Fetches an article from the given URL, extracts relevant information,
    analyzes the content using DeepSeek, and stores both the article
    and its analysis in the SQLite database.
    """
    try:
        logging.info(f"Fetching URL: {url}")
        # Make an HTTP GET request to fetch the article
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP errors

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract the article title
        try:
            title_tag = soup.find('h1')
            if title_tag:
                title = title_tag.get_text(strip=True)
                logging.info(f"Title found: {title}")
            else:
                logging.error("Title tag <h1> not found.")
                return
        except Exception as e:
            logging.error(f"Error extracting title: {e}")
            return

        # Extract the publication date with updated selector
        try:
            pub_date_tag = soup.find('span', class_='d-ib mr-05')
            if pub_date_tag:
                pub_date = pub_date_tag.get_text(strip=True)
                logging.info(f"Publication Date found: {pub_date}")
            else:
                logging.error("Publication date tag <span class='d-ib mr-05'> not found.")
                return
        except Exception as e:
            logging.error(f"Error extracting publication date: {e}")
            return

        # Extract the article body (adjusted selector)
        try:
            body_div = soup.find('div', class_='kInstance-Body instance-box-mb')
            if body_div:
                paragraphs = body_div.find_all('p')
                if paragraphs:
                    body_text = '\n\n'.join([para.get_text(strip=True) for para in paragraphs])
                    logging.info("Article body extracted successfully.")
                else:
                    logging.error("No <p> tags found within the article body.")
                    return
            else:
                logging.error("Article body div <div class='kInstance-Body instance-box-mb'> not found.")
                return
        except Exception as e:
            logging.error(f"Error extracting article body: {e}")
            return

        # Check if the article already exists
        try:
            existing_article = session.query(Article).filter_by(url=url).first()
            if existing_article:
                logging.info(f"Article already exists in the database: {title}")
                # Check if analysis already exists
                existing_analysis = session.query(AnalysisResult).filter_by(article_id=existing_article.id).first()
                if existing_analysis:
                    logging.info(f"Analysis already exists for article ID {existing_article.id}. Skipping analysis.")
                else:
                    logging.info(f"No analysis found for article ID {existing_article.id}. Performing analysis.")
                    analysis = analyze_article(body_text)
                    if analysis:
                        # Create a new AnalysisResult object
                        analysis_result = AnalysisResult(
                            article_id=existing_article.id,
                            company_name=analysis.get("company_name", ""),
                            ceo_name=analysis.get("ceo_name", ""),
                            summary=analysis.get("summary", "")
                        )

                        # Add to session and commit
                        session.add(analysis_result)
                        session.commit()

                        logging.info(f"Analysis saved for article ID {existing_article.id}")
                    else:
                        logging.error("Failed to analyze the article.")
                return existing_article.id
        except Exception as e:
            logging.error(f"Error querying the database: {e}")
            return

        # Create a new Article object
        try:
            article = Article(
                url=url,
                title=title,
                publication_date=pub_date,
                body_text=body_text
            )

            # Add to session and commit
            session.add(article)
            session.commit()

            logging.info(f"Scraped and saved article: {title}")

            # Analyze the article using DeepSeek
            analysis = analyze_article(body_text)
            if analysis:
                # Create a new AnalysisResult object
                analysis_result = AnalysisResult(
                    article_id=article.id,
                    company_name=analysis.get("company_name", ""),
                    ceo_name=analysis.get("ceo_name", ""),
                    summary=analysis.get("summary", "")
                )

                # Add to session and commit
                session.add(analysis_result)
                session.commit()

                logging.info(f"Analysis saved for article ID {article.id}")
            else:
                logging.error("Failed to analyze the article.")

            return article.id
        except SQLAlchemyError as e:
            logging.error(f"Database error: {e}")
            session.rollback()
            return
        except Exception as e:
            logging.error(f"Error saving article or analysis: {e}")
            session.rollback()
            return

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")  # e.g., 404 Not Found
    except Exception as err:
        logging.error(f"An unexpected error occurred: {err}")

if __name__ == "__main__":
    # List of article URLs to scrape
    article_urls = [
        'https://www.bizcommunity.com/article/2024-in-app-purchase-revenue-up-to-150bn-but-app-downloads-decrease-708972a',
        'https://www.bizcommunity.com/article/key-trends-for-local-smes-and-entrepreneurs-in-2025-475919a',
        # Add more URLs here
    ]

    for url in article_urls:
        article_id = fetch_and_store_article(url)
        if article_id:
            print(f"Article ID {article_id} saved.")
        else:
            print(f"Failed to save article from URL: {url}")