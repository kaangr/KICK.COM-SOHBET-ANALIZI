# NLP Analysis Functions (Sentiment, Topic Modeling)

from textblob import TextBlob
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from gensim import corpora, models
import gensim
import os # Added for cpu_count
from gensim.models import CoherenceModel # Added
import time # Added for timing
import streamlit as st # Needed for caching
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline # Import transformers components
import torch # Add torch import for GPU check
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # Added for VADER

# Ensure NLTK data is downloaded (users should run this once)
# try:
#     stopwords.words('english')
#     stopwords.words('turkish')
#     nltk.data.find('tokenizers/punkt')
#     nltk.data.find('corpora/wordnet')
# except LookupError:
#     print("Downloading NLTK data (stopwords, punkt, wordnet)...")
#     nltk.download('stopwords', quiet=True)
#     nltk.download('punkt', quiet=True)
#     nltk.download('wordnet', quiet=True)
#     print("NLTK data downloaded.")


# Combine English and Turkish stopwords
stop_words = set(stopwords.words('english')) | set(stopwords.words('turkish'))
lemmatizer = WordNetLemmatizer()

# Add custom chat/Turkish informal/slang/emote text stopwords
custom_stopwords = {
    # Turkish Informal & Common
    'abi', 'kanka', 'aga', 'knk', 'reyiz', 'reis', 'hocam', 'orda', 'burda', 'şurda',
    'yani', 'şey', 'ben', 'sen', 'biz', 'siz', 'onlar', 'bu', 'şu', 'o',
    'ama', 'veya', 'yada', 'gibi', 'ile', 'için', 'mi', 'mı', 'mu', 'mü',
    'bi', 'bir', 'be', 'de', 'da', 'ki', 'ne', 'ya', 'hee', 'yaw', 'yav',
    'çok', 'az', 'var', 'yok', 'evet', 'hayır',
    # English Informal & Common
    'bro', 'bruh', 'dude', 'pls', 'plz', 'ffs', 'gg', 'wp', 'ez', 'ngl', 'smh', 'tbh',
    'btw', 'aka', 'afk', 'rn', 'imo', 'imho',
    # Emote Text & Reactions
    'lul', 'lol', 'kekw', 'omegalul', 'pog', 'poggers', 'pogchamp', 'kappa', 'pepega',
    'residentsleeper', 'sadge', 'copium', 'monkas', 'feelsbadman', 'feelsgoodman',
    'haha', 'hehe', 'hihi',
    # Common commands/symbols if not filtered earlier
    # 'f', # Keep 'F' if "Press F" is a meaningful topic
    # Potentially filter expletives if they dominate topics negatively
    'wtf', 'lmao', 'amk', 'aq', 'zort','oe','oç','oc',
    # Add more as needed based on your specific chat logs
}

stop_words = stop_words.union(custom_stopwords)

# Minimum word length to keep
MIN_WORD_LENGTH = 3

def preprocess_text(text):
    """Cleans, tokenizes, and lemmatizes text for topic modeling."""
    text = str(text).lower()  # Lowercase

    # Remove URLs first
    text = re.sub(r'http\S+', '', text)

    # Simple check for bot commands (remove if message starts with !)
    if text.strip().startswith('!'):
        return [] # Return empty list for commands

    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\d+', '', text)      # Remove numbers
    tokens = word_tokenize(text)         # Tokenize

    processed_tokens = []
    for word in tokens:
        # Apply stopword and length filtering
        if word not in stop_words and len(word) >= MIN_WORD_LENGTH:
            # Lemmatize English words (best effort)
            try:
                processed_tokens.append(lemmatizer.lemmatize(word))
            except Exception:
                processed_tokens.append(word) # Keep original if error

    return processed_tokens


# --- Sentiment Analysis ---
def get_textblob_sentiment(text):
    """Classifies the sentiment of a text string using TextBlob."""
    # Ensure text is a string
    text = str(text)
    analysis = TextBlob(text)
    # Polarity is between -1 (negative) and 1 (positive)
    if analysis.sentiment.polarity > 0.1:  # Threshold for positive
        return 'positive'
    elif analysis.sentiment.polarity < -0.1: # Threshold for negative
        return 'negative'
    else:
        return 'neutral'

def perform_textblob_sentiment_analysis(messages: pd.Series) -> pd.Series:
    """Applies TextBlob sentiment analysis to a Pandas Series of messages."""
    # Handle potential NaN values by filling them with an empty string
    sentiments = messages.fillna('').apply(get_textblob_sentiment)
    return sentiments

# --- VADER Sentiment Analysis ---
@st.cache_resource
def load_vader_analyzer():
    """Loads the VADER SentimentIntensityAnalyzer."""
    return SentimentIntensityAnalyzer()

def get_vader_sentiment(text, analyzer):
    """Classifies sentiment using VADER's compound score."""
    text = str(text) # Ensure text is string
    vs = analyzer.polarity_scores(text)
    if vs['compound'] >= 0.05:
        return 'positive'
    elif vs['compound'] <= -0.05:
        return 'negative'
    else:
        return 'neutral'

def perform_vader_sentiment_analysis(messages: pd.Series) -> pd.Series:
    """Applies VADER sentiment analysis to a Pandas Series of messages."""
    analyzer = load_vader_analyzer()
    # Handle potential NaN values by filling them with an empty string
    sentiments = messages.fillna('').apply(lambda text: get_vader_sentiment(text, analyzer))
    return sentiments

# --- NEW: BERT Sentiment Analysis using Hugging Face ---

# Use st.cache_resource to load the model and tokenizer only once
@st.cache_resource
def load_bert_sentiment_pipeline():
    """Loads the Turkish BERT sentiment analysis model and tokenizer."""
    try:
        model_name = "savasy/bert-base-turkish-sentiment-cased"
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # Determine device: GPU if available, otherwise CPU
        device = 0 if torch.cuda.is_available() else -1 
        if torch.cuda.is_available():
            print("CUDA is available. Using GPU for BERT sentiment analysis.")
        else:
            print("CUDA not available. Using CPU for BERT sentiment analysis.")
            
        sentiment_analyzer = pipeline("sentiment-analysis", tokenizer=tokenizer, model=model, device=device)
        print(f"BERT Sentiment model '{model_name}' loaded successfully on {'GPU' if device != -1 else 'CPU'}.") # Log success and device
        return sentiment_analyzer
    except Exception as e:
        print(f"Error loading BERT model: {e}") # Log error
        st.error(f"Error loading BERT model '{model_name}': {e}. Ensure internet connection and model availability.")
        return None

def perform_bert_sentiment_analysis_turkish(messages: pd.Series) -> pd.Series:
    """
    Performs sentiment analysis on a Pandas Series of Turkish text messages 
    using a pre-trained BERT model from Hugging Face.

    Args:
        messages (pd.Series): A Pandas Series containing the text messages.

    Returns:
        pd.Series: A Pandas Series containing sentiment labels ('positive' or 'negative').
                   Returns an empty Series if the model could not be loaded.
    """
    sentiment_pipeline = load_bert_sentiment_pipeline()
    
    if sentiment_pipeline is None:
        return pd.Series(dtype='object') # Return empty series if model failed to load

    # Convert Series to list for pipeline processing
    message_list = messages.astype(str).fillna('').tolist() # Ensure strings and handle NaN

    # Filter out empty strings from message_list to avoid sending them to the pipeline
    # and keep track of original indices
    original_indices = []
    non_empty_messages = []
    for i, msg in enumerate(message_list):
        if msg.strip(): # Only process non-empty messages
            non_empty_messages.append(msg)
            original_indices.append(messages.index[i])
        # else: # Optionally handle empty messages if needed, e.g. assign 'neutral' or 'unknown'
            # print(f"Skipping empty message at original index: {messages.index[i]}")


    if not non_empty_messages:
        st.warning("No non-empty messages to analyze for BERT sentiment.")
        # Return a series of 'unknown' with the original index if all messages were empty
        return pd.Series(['unknown'] * len(messages), index=messages.index, dtype='object')

    try:
        # The pipeline can often handle lists directly and efficiently
        raw_results = sentiment_pipeline(non_empty_messages, truncation=True, max_length=512) # Added truncation
        
        print(f"Raw BERT sentiment results (sample of first 5): {raw_results[:5]}") # Log a sample of raw results

        # Initialize sentiments with 'unknown' for all original messages
        sentiments_dict = {idx: 'unknown' for idx in messages.index}

        # Map results to 'positive' or 'negative' based on original indices
        for i, result in enumerate(raw_results):
            original_idx = original_indices[i] # Get the original index for this result
            label = result.get('label') # Use .get() for safer access
            # Adjust to the actual labels returned by the model
            if label == 'positive': # Changed from 'LABEL_1'
                sentiments_dict[original_idx] = 'positive'
            elif label == 'negative': # Changed from 'LABEL_0'
                sentiments_dict[original_idx] = 'negative'
            # Optional: Handle neutral if the model provides it, or map other labels
            # elif label == 'neutral': 
            #     sentiments_dict[original_idx] = 'neutral'
            else:
                print(f"Unexpected label from BERT model: {label} for message: {non_empty_messages[i]}")
                sentiments_dict[original_idx] = 'unknown' # Keep as unknown if label is still unexpected

        # Convert the dictionary to a Series, ensuring it aligns with the original message index
        final_sentiments = pd.Series(sentiments_dict).reindex(messages.index)


    except Exception as e:
        st.error(f"Error during BERT sentiment analysis pipeline: {e}")
        # Return a series of 'unknown' with the original index on error
        return pd.Series(['unknown'] * len(messages), index=messages.index, dtype='object') 

    return final_sentiments # Ensure index alignment with input

# --- Custom Fine-Tuned Kick BERT Sentiment Analysis ---
@st.cache_resource
def load_custom_kick_bert_pipeline():
    """Loads the custom fine-tuned Kick BERT sentiment analysis model and tokenizer."""
    try:
        # Path to your fine-tuned model, relative to the NLP_Final directory (where analysis.py is)
        model_path = "kick_sentiment_project/model/finetuned_kick_sentiment"
        # Check if the model path exists
        if not os.path.exists(model_path):
            st.error(f"Custom model path not found: {os.path.abspath(model_path)}. Please ensure the model is trained and saved correctly.")
            print(f"Error: Custom model path not found: {os.path.abspath(model_path)}")
            return None
            
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        device = 0 if torch.cuda.is_available() else -1 
        if torch.cuda.is_available():
            print("CUDA is available. Using GPU for Custom Kick BERT sentiment analysis.")
        else:
            print("CUDA not available. Using CPU for Custom Kick BERT sentiment analysis.")
            
        sentiment_analyzer = pipeline("sentiment-analysis", tokenizer=tokenizer, model=model, device=device)
        print(f"Custom Kick BERT Sentiment model loaded successfully from '{model_path}' on {'GPU' if device != -1 else 'CPU'}.")
        return sentiment_analyzer
    except Exception as e:
        print(f"Error loading Custom Kick BERT model: {e}")
        st.error(f"Error loading Custom Kick BERT model from '{model_path}': {e}.")
        return None

def perform_custom_kick_bert_analysis(messages: pd.Series) -> pd.Series:
    """
    Performs sentiment analysis using the custom fine-tuned Kick BERT model.
    Args:
        messages (pd.Series): A Pandas Series containing the text messages.
    Returns:
        pd.Series: A Pandas Series containing sentiment labels.
    """
    sentiment_pipeline = load_custom_kick_bert_pipeline()
    
    if sentiment_pipeline is None:
        return pd.Series(['unknown'] * len(messages), index=messages.index, dtype='object') # Return unknown if model failed

    message_list = messages.astype(str).fillna('').tolist()
    original_indices = []
    non_empty_messages = []
    for i, msg in enumerate(message_list):
        if msg.strip():
            non_empty_messages.append(msg)
            original_indices.append(messages.index[i])

    if not non_empty_messages:
        st.warning("No non-empty messages to analyze for Custom Kick BERT sentiment.")
        return pd.Series(['unknown'] * len(messages), index=messages.index, dtype='object')

    sentiments_dict = {idx: 'unknown' for idx in messages.index}
    try:
        raw_results = sentiment_pipeline(non_empty_messages, truncation=True, max_length=512)
        print(f"Raw Custom Kick BERT sentiment results (sample of first 5): {raw_results[:5]}")

        # Define the expected order of labels from your LabelEncoder during training
        # le.classes_ was ['negative', 'neutral', 'positive']
        # So, LABEL_0 is negative, LABEL_1 is neutral, LABEL_2 is positive
        label_map = { 
            "LABEL_0": "negative", 
            "LABEL_1": "neutral", 
            "LABEL_2": "positive",
            # Add direct integer mappings as well, in case the model outputs integers
            0: "negative",
            1: "neutral",
            2: "positive"
        }

        for i, result in enumerate(raw_results):
            original_idx = original_indices[i]
            raw_label = result.get('label') # This could be 'LABEL_0', 0, 'LABEL_1', 1 etc.
            
            # Get the string sentiment from our map
            # The .get() on label_map will return None if raw_label is not a key
            sentiment = label_map.get(raw_label)
            
            if sentiment:
                sentiments_dict[original_idx] = sentiment
            else:
                print(f"Unexpected label from Custom Kick BERT model: {raw_label} for message: {non_empty_messages[i]}. Check label mapping.")
                sentiments_dict[original_idx] = 'unknown' 

        final_sentiments = pd.Series(sentiments_dict).reindex(messages.index)

    except Exception as e:
        st.error(f"Error during Custom Kick BERT sentiment analysis pipeline: {e}")
        return pd.Series(['unknown'] * len(messages), index=messages.index, dtype='object') 

    return final_sentiments

# --- New Main Sentiment Dispatcher ---
def run_sentiment_analysis(messages: pd.Series, method: str = 'bert') -> pd.Series:
    """
    Runs sentiment analysis using the specified method.

    Args:
        messages (pd.Series): A Pandas Series containing the text messages.
        method (str): The sentiment analysis method to use.
                      Options: 'textblob', 'bert', 'vader', 'custom_kick_bert'. Defaults to 'bert'.

    Returns:
        pd.Series: A Pandas Series containing sentiment labels.
    """
    if method == 'textblob':
        print("Running sentiment analysis using TextBlob...")
        return perform_textblob_sentiment_analysis(messages)
    elif method == 'bert':
        print("Running sentiment analysis using BERT...")
        return perform_bert_sentiment_analysis_turkish(messages)
    elif method == 'vader':
        print("Running sentiment analysis using VADER...")
        return perform_vader_sentiment_analysis(messages)
    elif method == 'custom_kick_bert':
        print("Running sentiment analysis using Custom Fine-Tuned Kick BERT...")
        return perform_custom_kick_bert_analysis(messages)
    else:
        st.error(f"Unknown sentiment analysis method: {method}. Supported methods are 'textblob', 'bert', 'vader', and 'custom_kick_bert'.")
        # Return neutral for all if method is unknown, or handle as preferred
        return pd.Series(['neutral'] * len(messages), index=messages.index, dtype='object')

# --- Topic Modeling ---
def perform_topic_modeling(messages: pd.Series, num_topics=5, num_words=5):
    """Performs LDA topic modeling and calculates coherence.
    Returns: lda_model, topics, coherence_score, duration_seconds
    """
    start_time = time.time() # Start timing

    processed_docs = messages.fillna('').apply(preprocess_text)
    processed_docs = [doc for doc in processed_docs if doc]
    
    if not processed_docs:
        print("Warning: No processable documents found for topic modeling.")
        # Return None for model, empty dict for topics, None for score, and 0 duration
        return None, {}, None, 0

    dictionary = corpora.Dictionary(processed_docs)
    corpus = [dictionary.doc2bow(doc) for doc in processed_docs]

    if not corpus:
        print("Warning: Corpus is empty after creating Bag-of-Words.")
        # Return None for model, empty dict for topics, None for score, and 0 duration
        return None, {}, None, 0

    lda_model = None
    topics = {}
    coherence_score = None
    try:
        # Determine number of workers for LdaMulticore
        # Use all cores except one, but default to 1 if cpu_count fails
        try:
            workers = max(1, os.cpu_count() - 1)
        except NotImplementedError:
            workers = 1
            print("Warning: Could not determine CPU count. Defaulting to 1 worker.")

        # Prefer LdaMulticore if multiple workers can be used
        if workers > 1:
            print(f"Using LdaMulticore with {workers} workers.")
            lda_model = gensim.models.LdaMulticore(corpus=corpus,
                                               id2word=dictionary,
                                               num_topics=num_topics,
                                               random_state=100,
                                               chunksize=100,
                                               passes=10,
                                               workers=workers)
        # Fallback to LdaModel if only 1 worker is available
        else:
            print("Using standard LdaModel (single core).")
            lda_model = gensim.models.LdaModel(corpus=corpus,
                                           id2word=dictionary,
                                           num_topics=num_topics,
                                           random_state=100,
                                           update_every=1,
                                           chunksize=100,
                                           passes=10,
                                           alpha='auto',
                                           per_word_topics=True)

        if lda_model:
            # Get topics
            formatted_topics = {i: [(word, f"{weight:.3f}") for word, weight in lda_model.show_topic(i, topn=num_words)] 
                                for i in range(min(num_topics, lda_model.num_topics))}
            
            # Calculate Coherence Score (C_v)
            try:
                coherence_model_lda = CoherenceModel(model=lda_model, 
                                                   texts=processed_docs, 
                                                   dictionary=dictionary, 
                                                   coherence='c_v')
                coherence_score = coherence_model_lda.get_coherence()
                print(f"Coherence Score (C_v): {coherence_score}")
            except Exception as ce:
                print(f"Warning: Could not calculate coherence score: {ce}")
                coherence_score = None
                
            end_time = time.time() # End timing
            duration = end_time - start_time
            print(f"Topic modeling duration: {duration:.2f} seconds")

            return lda_model, formatted_topics, coherence_score, duration # Return duration
        else:
             print("Error: LDA model was not successfully trained.")
             # Return None/empty values and 0 duration on failure
             return None, {}, None, 0
        
    except Exception as e:
        print(f"Error during LDA model training or coherence calculation: {e}")
        # Return None/empty values and 0 duration on error
        return None, {}, None, 0

# --- Content Suggestions ---
def generate_content_suggestions(df: pd.DataFrame, topics: dict) -> list[str]:
    """Generates basic content suggestions based on sentiment and topics."""
    suggestions = []
    
    if df.empty or 'sentiment' not in df.columns:
        return ["Not enough data for suggestions."]
        
    # Suggestion 1: Overall Sentiment
    overall_sentiment = df['sentiment'].mode() # Most frequent sentiment
    if not overall_sentiment.empty:
        sentiment_mode = overall_sentiment[0]
        if sentiment_mode == 'positive':
            suggestions.append("Overall chat sentiment is positive! Keep up the great engagement.")
        elif sentiment_mode == 'negative':
            suggestions.append("Consider addressing potential concerns, as overall sentiment leans negative.")
        else:
            suggestions.append("Chat sentiment is mostly neutral. Look for opportunities to boost engagement.")
            
    # Suggestion 2: Popular Topics (requires LDA model output)
    if topics:
        # Simple approach: Find the topic with the 'highest weight' keywords overall? 
        # Or just list the top few keywords from the first topic as an example
        try:
            top_topic_keywords = [word for word, weight in topics[0]] # Keywords from Topic 1
            suggestions.append(f"Top discussion keywords include: {', '.join(top_topic_keywords)}. Consider focusing on these.")
            
            # Potential future enhancement: Link topics to sentiment
            # For example, find messages associated with a topic and check their average sentiment.
            
        except (KeyError, IndexError):
             suggestions.append("Could not extract keywords from topics for suggestions.")
             
    else:
        suggestions.append("Topic modeling did not produce results for suggestions.")

    # Suggestion 3: Negative Sentiment Keywords (simple approach)
    negative_messages = df[df['sentiment'] == 'negative']['message']
    if not negative_messages.empty:
        # Very basic: Look at common words in negative messages after preprocessing
        processed_negative = negative_messages.fillna('').apply(preprocess_text)
        all_negative_words = [word for sublist in processed_negative for word in sublist]
        if all_negative_words:
            negative_freq = pd.Series(all_negative_words).value_counts()
            top_negative_words = negative_freq.head(3).index.tolist()
            suggestions.append(f"Keywords associated with negative sentiment include: {', '.join(top_negative_words)}. Be mindful of discussions around these.")

    if not suggestions:
        return ["No specific suggestions could be generated at this time."]
        
    return suggestions 