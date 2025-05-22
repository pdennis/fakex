import os
import random
import re
import time
import threading
import queue
from flask import Flask, render_template, jsonify
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import requests
import glob

# Configuration
BOOK_LIBRARY_PATH = "/Volumes/mangohd/Books/newLibrary"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:12b"
WORDS_PER_PASSAGE = 500

app = Flask(__name__)

# Queue for book processing
tweet_queue = queue.Queue(maxsize=10)
tweets = []

def get_random_book_path():
    """Get a random book path from the library"""
    # Get all author directories
    author_dirs = [d for d in os.listdir(BOOK_LIBRARY_PATH) 
                  if os.path.isdir(os.path.join(BOOK_LIBRARY_PATH, d)) and not d.startswith('.')]
    
    if not author_dirs:
        return None
    
    # Select a random author
    author = random.choice(author_dirs)
    author_path = os.path.join(BOOK_LIBRARY_PATH, author)
    
    # Get all book directories for this author
    book_dirs = [d for d in os.listdir(author_path) 
                if os.path.isdir(os.path.join(author_path, d))]
    
    if not book_dirs:
        return None
    
    # Select a random book
    book_dir = random.choice(book_dirs)
    book_path = os.path.join(author_path, book_dir)
    
    # Find ebook files (epub, pdf, txt)
    ebook_files = []
    for ext in ['*.epub', '*.txt', '*.pdf']:
        ebook_files.extend(glob.glob(os.path.join(book_path, ext)))
    
    if not ebook_files:
        return None
    
    return random.choice(ebook_files)

def extract_text_from_epub(epub_path):
    """Extract text from an EPUB file"""
    try:
        book = epub.read_epub(epub_path)
        text = ""
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text += soup.get_text() + "\n"
        
        return text
    except Exception as e:
        print(f"Error extracting text from EPUB: {e}")
        return ""

def extract_text_from_txt(txt_path):
    """Extract text from a TXT file"""
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Error extracting text from TXT: {e}")
        return ""

def extract_book_info(file_path):
    """Extract book information and a random passage"""
    # Ensure randomness by reseeding
    random.seed()
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # Extract author and title from path
    path_parts = file_path.split(os.sep)
    author = path_parts[-3]  # Author directory is typically 2 levels up from the file
    
    # Try to extract title from filename or directory
    title = path_parts[-2]  # Book directory name
    if "(" in title:  # Remove anything in parentheses like "(238)"
        title = re.sub(r'\s*\([^)]*\)', '', title).strip()
    
    # Extract text based on file type
    if file_ext == '.epub':
        text = extract_text_from_epub(file_path)
    elif file_ext == '.txt':
        text = extract_text_from_txt(file_path)
    else:
        # For PDF or other formats we don't handle yet
        text = f"Unable to extract text from {file_ext} files yet."
    
    # If we have text, get a random passage
    passage = ""
    if text and len(text) > 1000:
        # Clean text: remove excessive whitespace and normalize
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split text into chunks (roughly sentence or paragraph based)
        chunks = re.split(r'(?<=[.!?])\s+', text)
        
        if len(chunks) > 5:  # Need at least a few chunks to get a coherent passage
            # Choose a random starting chunk, but avoid the very beginning and end
            start_chunk = random.randint(2, len(chunks) - 10) if len(chunks) > 12 else 0
            
            # Build passage until we have enough words or reach the end
            current_words = 0
            passage_chunks = []
            
            while current_words < WORDS_PER_PASSAGE and start_chunk < len(chunks):
                passage_chunks.append(chunks[start_chunk])
                current_words += len(chunks[start_chunk].split())
                start_chunk += 1
            
            passage = ' '.join(passage_chunks)
            
            # Trim to approximately WORDS_PER_PASSAGE if we went over
            if current_words > WORDS_PER_PASSAGE * 1.2:
                passage_words = passage.split()
                passage = ' '.join(passage_words[:WORDS_PER_PASSAGE])
    
    return {
        "author": author,
        "title": title,
        "passage": passage,
        "file_path": file_path
    }

def generate_tweet(book_info):
    """Generate a tweet about the book passage using Ollama"""
    prompt = f"""
    Author: {book_info['author']}
    Title: {book_info['title']}
    
    Passage:
    {book_info['passage']}
    
    Task: Use this passage, and the context around it (the author, etc) as the inspiration for a tweet. It should not simply be a summary of the passage. Extract an interesting idea, identify a meta-concept or the author's decision making, or tie an idea from the passage to a historical event or another work.  No hashtags. Only output tweet text. 
    Be interesting and thought-provoking.  400 characters or less. Do not phrase your post as a question, make it a statement.
    """
    
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            tweet_text = result.get("response", "").strip()
            # Truncate to 280 chars if needed
            if len(tweet_text) > 280:
                tweet_text = tweet_text[:277] + "..."
            
            return {
                "author": book_info['author'],
                "title": book_info['title'],
                "tweet": tweet_text,
                "timestamp": time.time()
            }
        else:
            return {
                "author": book_info['author'],
                "title": book_info['title'],
                "tweet": f"Failed to generate tweet: {response.status_code}",
                "timestamp": time.time()
            }
    except Exception as e:
        return {
            "author": book_info['author'],
            "title": book_info['title'],
            "tweet": f"Error generating tweet: {str(e)}",
            "timestamp": time.time()
        }

def tweet_generator():
    """Background thread to generate tweets"""
    # Keep track of recently used books to avoid repeats
    recent_books = set()
    max_recent = 20  # Remember the last 20 books
    
    while True:
        try:
            # Reseed random to ensure true randomness
            random.seed()
            
            # Get a random book that hasn't been used recently
            attempts = 0
            max_attempts = 10
            book_path = None
            
            while attempts < max_attempts:
                book_path = get_random_book_path()
                # Check if book was used recently
                if book_path and book_path not in recent_books:
                    break
                attempts += 1
            
            if book_path:
                # Add to recently used set
                recent_books.add(book_path)
                if len(recent_books) > max_recent:
                    recent_books.pop()  # Remove oldest book
                
                # Extract book info
                book_info = extract_book_info(book_path)
                if book_info['passage']:
                    # Generate tweet
                    tweet = generate_tweet(book_info)
                    
                    # Add to queue if not full
                    if not tweet_queue.full():
                        # Add microsecond precision to timestamp to ensure uniqueness
                        tweet['timestamp'] = time.time()
                        tweet_queue.put(tweet)
                        print(f"Generated new tweet from: {tweet['author']} - {tweet['title']}")
                        
            # Sleep for a bit to avoid hammering the filesystem
            time.sleep(5)
        except Exception as e:
            print(f"Error in tweet generator: {e}")
            time.sleep(10)  # Sleep longer on error

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/tweets')
def get_tweets():
    """API endpoint to get tweets"""
    # Check for new tweets in the queue
    while not tweet_queue.empty():
        try:
            tweet = tweet_queue.get_nowait()
            tweets.append(tweet)
            # Keep only the most recent 100 tweets
            if len(tweets) > 100:
                tweets.pop(0)
        except queue.Empty:
            break
    
    # Return all tweets in reverse chronological order (newest first)
    return jsonify(sorted(tweets, key=lambda x: x['timestamp'], reverse=True))

if __name__ == '__main__':
    # Start the tweet generator thread
    generator_thread = threading.Thread(target=tweet_generator, daemon=True)
    generator_thread.start()
    
    # Run the Flask app on port 5001 instead of default 5000 (which is used by macOS)
    app.run(debug=True, port=5001)