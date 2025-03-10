import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request
from markupsafe import Markup
import markdown
import json
import os
import feedparser
import time
import google.api_core.exceptions

# Configure Gemini API
genai.configure(api_key="AIzaSyAy9BuATxWMgEjgedB13u1LvyNN5INWYRQ")

def fetch_jmlr_articles():
    """Fetches recent articles from JMLR."""
    jmlr_url = "http://www.jmlr.org/jmlr.xml"
    feed = feedparser.parse(jmlr_url)

    articles = []
    for entry in feed.entries[:10]:  # Fetch the 10 most recent articles
        title = entry.title
        summary = entry.summary  # JMLR provides abstracts in the summary field
        link = entry.link

        articles.append({"title": title, "summary": summary, "link": link})
    
    return articles

def fetch_arxiv_papers(selected_topics):
    """Fetches recent papers from arXiv based on selected topics."""
    
    topic_mapping = {
        "Arxiv AI": "cs.AI",
        "Arxiv ML": "cs.LG",
        "Arxiv CV": "cs.CV",
        "Arxiv NN": "cs.NE",
        "Arxiv StatsML": "stat.ML"
    }

    query_topics = "+OR+".join([f"cat:{topic_mapping[t]}" for t in selected_topics if t in topic_mapping])
    url = f"http://export.arxiv.org/api/query?search_query={query_topics}&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending"

    response = requests.get(url)
    root = ET.fromstring(response.content)

    papers = []
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        title = entry.find("{http://www.w3.org/2005/Atom}title").text
        summary = entry.find("{http://www.w3.org/2005/Atom}summary").text
        link = entry.find("{http://www.w3.org/2005/Atom}id").text
        
        papers.append({"title": title, "summary": summary, "link": link})
    
    return papers

# def summarize_with_gemini(text):
#     """Summarizes text using Gemini AI API with caching."""
#     cache_file = "summaries_cache.json"
    
#     if os.path.exists(cache_file):
#         with open(cache_file, "r") as f:
#             cache = json.load(f)
#     else:
#         cache = {}

#     if text in cache:
#         return cache[text]
    
#     # Generate summary using Gemini
#     prompt = f"Summarize this research paper and provide key ideas and main points. Include key mathematical ideas or results as well:\n{text}\n\n."
#     response = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt)

#     summary = response.text if response else "Summary not available."
    
#     cache[text] = summary
#     with open(cache_file, "w") as f:
#         json.dump(cache, f)
    
#     return summary

def summarize_with_gemini(text):
    """Summarizes text using Gemini AI API with caching and error handling."""
    cache_file = "summaries_cache.json"
    
    # Load existing cache
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)
    else:
        cache = {}

    # Return cached summary if available
    if text in cache:
        return cache[text]

    prompt = f"Summarize this research paper and provide key ideas:\n{text}\n\n."

    retries = 3  # Retry up to 3 times
    for attempt in range(retries):
        try:
            response = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt)
            summary = response.text if response else "Summary not available."
            
            # Save in cache
            cache[text] = summary
            with open(cache_file, "w") as f:
                json.dump(cache, f)
            
            return summary

        except google.api_core.exceptions.ResourceExhausted:
            print(f"Quota exceeded. Retrying in {2 ** attempt} seconds...")
            time.sleep(2 ** attempt)  # Exponential backoff (2s, 4s, 8s)
        except Exception as e:
            print(f"Unexpected error: {e}")
            break

    return "Daily API quota exceeded. Try again later!"


app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def home():
    if os.path.exists("summaries_cache.json"):
        os.remove("summaries_cache.json")

    selected_topics = request.form.getlist('topics')  
    if not selected_topics:
        selected_topics = ["Arxiv AI"]  # Ensure only "Arxiv AI" is selected by default

    arxiv_papers = fetch_arxiv_papers(selected_topics) if any(t.startswith("Arxiv") for t in selected_topics) else []
    jmlr_papers = fetch_jmlr_articles() if "JMLR" in selected_topics else []

    summarized_arxiv = []
    summarized_jmlr = []

    for paper in arxiv_papers:
        summary = summarize_with_gemini(paper['summary'])
        summary_html = Markup(markdown.markdown(summary))  
        summarized_arxiv.append({"title": paper['title'], "summary": summary_html, "link": paper['link']})

    for article in jmlr_papers:
        summary = summarize_with_gemini(article['summary'])
        summary_html = Markup(markdown.markdown(summary))
        summarized_jmlr.append({"title": article['title'], "summary": summary_html, "link": article['link']})
    
    return render_template('index.html', arxiv_papers=summarized_arxiv, jmlr_papers=summarized_jmlr, selected_topics=selected_topics)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, threaded = True)
