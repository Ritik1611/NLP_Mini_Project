from graphviz import Digraph

dot = Digraph(comment='Multilingual Emotion Detection System Architecture')
dot.attr(rankdir='LR', size='8,5')
dot.attr('node', shape='box', style='filled', fillcolor='lightyellow', color='black', fontname='Helvetica')

# User Interface
dot.node('UI', 'User Interface (Streamlit)\n• Input product name\n• Select optional brands\n• Run / Clear / Export\n• Shows logs & charts')

# Review Fetching
dot.node('Fetcher', 'Review Fetching Module\n• Uses SerpAPI for reviews\n• Extracts snippets & links\n• Handles retries & pacing')

# Brand Inference
dot.node('Brand', 'Brand Inference Module\n• Extracts brand names from reviews\n• Validates via LLM (Mistral)\n• Manages rate limits & verification')

# Emotion Detection
dot.node('Emotion', 'Emotion / Sentiment Module\n• Uses multilingual transformer (XLM-R / mBERT)\n• Detects emotion per review\n• Updates results in DB')

# Database Layer
dot.node('DB', 'Database Layer (SQLite)\n• Stores reviews, brands, emotions\n• CRUD operations\n• Caching & reprocessing')

# Visualization
dot.node('Viz', 'Visualization / Export Module\n• Brand-wise emotion charts\n• Comparison graphs\n• Export to CSV')

# Connect components
dot.edges([
    ('UI', 'Fetcher'),
    ('Fetcher', 'Brand'),
    ('Brand', 'Emotion'),
    ('Emotion', 'DB'),
    ('DB', 'Viz')
])
dot.edge('Viz', 'UI', label='Charts & CSV Export', color='darkgreen')

# Save and render
dot.render('emotion_detection_system_architecture', format='png', cleanup=True)

print("✅ Diagram saved as 'emotion_detection_system_architecture.png'")
