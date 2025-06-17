import streamlit as st
from openai import OpenAI
import fitz  # PyMuPDF
from docx import Document
from PIL import Image
import io
import base64
import json
import requests
from threading import Event, Thread
import time
import re
from typing import List, Dict, Any
import hashlib
from datetime import datetime

# --- Streamlit Cloud Content Protection System ---
def save_content_safely(content_type, content, grade_level=None):
    """Save content with multiple backup strategies for Streamlit Cloud"""
    if not content:
        return
    
    try:
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Strategy 1: Primary session state
        st.session_state[content_type] = content
        
        # Strategy 2: Multiple backup session states
        backup_data = {
            'content': content,
            'timestamp': timestamp,
            'hash': content_hash,
            'length': len(content)
        }
        
        st.session_state[f"{content_type}_backup_1"] = backup_data
        st.session_state[f"{content_type}_backup_2"] = backup_data.copy()
        st.session_state[f"{content_type}_backup_3"] = backup_data.copy()
        
        # Strategy 3: Browser localStorage (works on Streamlit Cloud)
        save_to_browser_storage(content_type, content, timestamp)
        
        # Strategy 4: Compressed backup for large content
        if len(content) > 10000:
            # Store truncated version as emergency backup
            emergency_backup = content[:5000] + "\n\n[CONTENT TRUNCATED - PARTIAL BACKUP]"
            st.session_state[f"{content_type}_emergency"] = emergency_backup
        
        # Mark as successfully saved
        st.session_state[f"{content_type}_saved_timestamp"] = timestamp
        
    except Exception as e:
        st.error(f"⚠️ Failed to save {content_type}: {e}")

def save_to_browser_storage(content_type, content, timestamp):
    """Save content to browser localStorage for persistence"""
    try:
        # Create minimal JavaScript to save to localStorage
        content_json = json.dumps(content).replace("'", "\\'")
        js_code = f"""
        <script>
        try {{
            localStorage.setItem('eeebee_{content_type}', '{content_json}');
            localStorage.setItem('eeebee_{content_type}_time', '{timestamp}');
            console.log('Saved {content_type} to localStorage');
        }} catch(e) {{
            console.warn('localStorage save failed:', e);
        }}
        </script>
        """
        st.components.v1.html(js_code, height=0)
    except Exception:
        # Fail silently for browser storage
        pass

def recover_content_safely(content_type):
    """Attempt to recover content from available backups"""
    recovered_content = None
    source = "none"
    
    # Check primary session state
    if st.session_state.get(content_type):
        recovered_content = st.session_state[content_type]
        source = "primary"
    
    # Check backup session states
    elif st.session_state.get(f"{content_type}_backup_1"):
        backup = st.session_state[f"{content_type}_backup_1"]
        recovered_content = backup.get('content')
        source = "backup_1"
    
    elif st.session_state.get(f"{content_type}_backup_2"):
        backup = st.session_state[f"{content_type}_backup_2"]
        recovered_content = backup.get('content')
        source = "backup_2"
    
    elif st.session_state.get(f"{content_type}_backup_3"):
        backup = st.session_state[f"{content_type}_backup_3"]
        recovered_content = backup.get('content')
        source = "backup_3"
    
    # Check emergency backup
    elif st.session_state.get(f"{content_type}_emergency"):
        recovered_content = st.session_state[f"{content_type}_emergency"]
        source = "emergency"
    
    return recovered_content, source

def verify_and_recover_all_content():
    """Check all content and recover if missing"""
    content_types = ['chapter_content', 'exercises', 'skill_activities', 'art_learning']
    recovered_any = False
    
    for content_type in content_types:
        current_content = st.session_state.get(content_type)
        
        if not current_content:
            recovered_content, source = recover_content_safely(content_type)
            if recovered_content:
                st.session_state[content_type] = recovered_content
                st.success(f"🔄 Recovered {content_type.replace('_', ' ')} from {source}")
                recovered_any = True
                
                # Re-save with all protection strategies
                save_content_safely(content_type, recovered_content)
    
    return recovered_any

def auto_save_during_streaming(content_type, partial_content, interval=1000):
    """Auto-save content during streaming at regular intervals"""
    if not partial_content:
        return
        
    # Save every ~1000 characters to prevent loss
    if len(partial_content) % interval < 50:
        save_content_safely(content_type, partial_content)

def display_content_status():
    """Display content status in sidebar for monitoring"""
    content_types = ['chapter_content', 'exercises', 'skill_activities', 'art_learning']
    
    with st.sidebar:
        st.markdown("### 💾 Content Status")
        for content_type in content_types:
            content = st.session_state.get(content_type)
            if content:
                saved_time = st.session_state.get(f"{content_type}_saved_timestamp", "Unknown")
                length = len(content)
                
                # Show status with emoji
                if saved_time != "Unknown":
                    status = "🟢"
                    time_str = saved_time[11:19] if len(saved_time) > 19 else saved_time
                else:
                    status = "🟡"
                    time_str = "Not saved"
                
                name = content_type.replace('_', ' ').title()
                st.markdown(f"{status} **{name}**")
                st.markdown(f"   📏 {length:,} chars | 🕒 {time_str}")
        
        # Recovery button
        if st.button("🔄 Check & Recover All", key="recover_all_content"):
            recovered = verify_and_recover_all_content()
            if not recovered:
                st.info("✅ All content is safe!")
            st.rerun()

# --- Configuration ---
# Get API key from Streamlit secrets
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    YOUR_SITE_URL = st.secrets.get("YOUR_SITE_URL", "https://your-site.com")
    YOUR_SITE_NAME = st.secrets.get("YOUR_SITE_NAME", "EeeBee Content Suite")
except KeyError:
    st.error("""
    🔑 **OpenRouter API Key Not Found!**
    
    Please add your OpenRouter API key to Streamlit secrets:
    
    **For local development:**
    Create a `.streamlit/secrets.toml` file in your project directory with:
    ```toml
    OPENROUTER_API_KEY = "your_openrouter_api_key_here"
    YOUR_SITE_URL = "https://your-site.com"  # Optional
    YOUR_SITE_NAME = "EeeBee Content Suite"  # Optional
    ```
    
    **For Streamlit Cloud deployment:**
    1. Go to your app's settings in Streamlit Cloud
    2. Click on "Secrets" 
    3. Add the following:
    ```toml
    OPENROUTER_API_KEY = "your_openrouter_api_key_here"
    YOUR_SITE_URL = "https://your-site.com"
    YOUR_SITE_NAME = "EeeBee Content Suite"
    ```
    
    **How to get an OpenRouter API Key:**
    1. Go to [OpenRouter](https://openrouter.ai/)
    2. Sign up and create an API key
    3. Copy the key and add it to your secrets
    """)
    st.stop()

# Initialize OpenAI Client with OpenRouter
try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    # Test the client
    models = client.models.list()
except Exception as e:
    st.error(f"Error configuring OpenRouter client: {e}")
    st.stop()

# Model to use
MODEL_NAME = "google/gemini-2.5-pro-preview"  # You can change this to "anthropic/claude-sonnet-4" when available

# --- Helper Functions ---

def load_model_chapter_progression(file_path="Model Chapter Progression and Elements.txt"):
    """Loads the model chapter progression text."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"Error: The file {file_path} was not found. Please make sure it's in the same directory as app.py.")
        return None

def extract_text_from_pdf(pdf_file_bytes):
    """Extracts text from PDF bytes."""
    text = ""
    try:
        doc = fitz.open(stream=pdf_file_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += f"\n\n--- Page {page_num + 1} ---\n"
            text += page.get_text()
        doc.close()
    except Exception as e:
        st.error(f"Could not extract text from PDF: {e}")
    return text

def extract_images_from_pdf(pdf_file_bytes):
    """Extracts images from PDF and returns them as base64 encoded strings."""
    images = []
    try:
        doc = fitz.open(stream=pdf_file_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                # Convert to base64
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                ext = base_image["ext"]
                images.append({
                    "page": page_num + 1,
                    "base64": f"data:image/{ext};base64,{base64_image}",
                    "description": f"Image from page {page_num + 1}"
                })
        doc.close()
    except Exception as e:
        st.warning(f"Could not extract images from PDF: {e}")
    return images

def create_messages_with_pdf_content(prompt, pdf_text, pdf_images=None):
    """Creates messages array for OpenAI API with PDF content."""
    messages = []
    
    # Add the main prompt with text content
    content_parts = [{"type": "text", "text": prompt}]
    
    # Add PDF text
    if pdf_text:
        content_parts.append({
            "type": "text", 
            "text": f"\n\nPDF Content:\n{pdf_text}"
        })
    
    # Add all images if available
    if pdf_images:  # No limit on number of images
        for img in pdf_images:  # Include all images
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": img["base64"],
                    "detail": "high"  # Use high detail for best quality
                }
            })
    
    messages.append({
        "role": "user",
        "content": content_parts
    })
    
    return messages

def analyze_with_llm(pdf_file_bytes, pdf_filename, model_progression_text, grade_level):
    """Analyzes the uploaded PDF chapter using OpenRouter API."""
    st.info("Extracting content from PDF...")
    
    # Extract text from PDF
    pdf_text = extract_text_from_pdf(pdf_file_bytes)
    if not pdf_text:
        return "Error: Could not extract text from PDF.", "Error"
    
    # Extract images (optional - you can disable this if token usage is too high)
    pdf_images = extract_images_from_pdf(pdf_file_bytes)
    
    prompt_content = f"""You are an expert in educational content development, specifically for CBSE curriculum.
Your task is to analyze the provided PDF document, which is a book chapter intended for **{grade_level} (CBSE)**.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes. Please proceed with the analysis and rewriting.

You need to evaluate it against the 'Model Chapter Progression and Elements' provided below.
The final output should be a completely rewritten and improved chapter that incorporates all necessary corrections and adheres to the model, suitable for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines. The book should be according to the NCERT books for **{grade_level}**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

**REQUIRED CONTENT STRUCTURE:**
The improved chapter MUST follow this specific structure:
1. Current Concepts
2. Hook (with Image Prompt)
3. Learning Outcome
4. Real world connection
5. Previous class concept
6. History
7. Summary
10. Exercise (with the following 5 question types, each with appropriate number of questions):
   - MCQ
   - Assertion and Reason
   - Fill in the Blanks
   - True False
   - Define the following terms
   - Match the column
   - Give Reason for the following Statement (Easy Level)
   - Answer in Brief (Moderate Level)
   - Answer in Detail (Hard Level)
11. Skill based Activity
12. Activity Time – STEM
13. Creativity – Art
14. Case Study – Level 1
15. Case Study – Level 2

**Target Audience:** {grade_level} (CBSE Syllabus)

**Important Formatting Requirements:**
* Format like a proper textbook with well-structured paragraphs (not too long but sufficiently developed)
* Use clear headings and subheadings to organize content
* Include multiple Bloom's Taxonomy questions at different levels in each relevant section
* Create concept-wise summaries (visuals are optional but helpful)
* Integrate special features within the core concept flow rather than as separate sections
* DO NOT change the original concept names/terminology from the uploaded PDF

**Instructions for Analysis and Rewrite:**
1.  **Read and understand the entire PDF chapter.** Pay attention to text, images, diagrams, and overall structure, keeping the **{grade_level}** student in mind.
2.  **Compare the chapter to each element** in the 'Model Chapter Progression and Elements'.
3.  **Identify deficiencies:** Where does the uploaded chapter fall short for a **{grade_level}** audience and the model? Be specific.
4.  **Analyze Images:** For each image in the PDF, assess its:
    *   Relevance to the surrounding text and learning objectives for **{grade_level}**.
    *   Clarity and quality.
    *   Age-appropriateness for **{grade_level}**.
    *   Presence of any specific characters if expected (e.g., 'EeeBee').
5.  **Suggest Image Actions:**
    *   If an image is good, state that it should be kept.
    *   If an image needs improvement (e.g., better clarity, different focus for **{grade_level}**), describe the improvement.
    *   If an image is irrelevant, unsuitable, or missing, provide a detailed prompt for an AI image generator to create a new, appropriate image suitable for **{grade_level}**. The prompt should be clearly marked, e.g., "[PROMPT FOR NEW IMAGE: A detailed description of the image needed, including style, content, characters like 'EeeBee' if applicable, and educational purpose for **{grade_level}**.]"
6.  **Rewrite the Chapter:** Create a new version of the chapter that:
    *   Follows the 'Model Chapter Progression and Elements' strictly.
    *   MUST include ALL elements from the REQUIRED CONTENT STRUCTURE in the order specified.
    *   Corrects all identified mistakes and deficiencies.
    *   Integrates image feedback directly into the text.
    *   Ensures content is aligned with NCERT, NCF, and NEP 2020 principles (e.g., inquiry-based learning, 21st-century skills, real-world connections) appropriate for **{grade_level}**.
    *   Is written in clear, engaging, and age-appropriate language for **{grade_level} (CBSE)**.
    *   Use Markdown for formatting (headings, bold, italics, lists) to make it easy to convert to a Word document. For example:
        # Chapter Title
        ## Section Title
        **Bold Text**
        *Italic Text*
        - Item 1
        - Item 2
    *   Present content in proper textbook paragraphs like a NCERT textbook
    *   Include multiple Bloom's Taxonomy questions at various levels (Remember, Understand, Apply, Analyze, Evaluate, Create) in each appropriate section
    *   Organize summaries by individual concepts rather than as a single summary
    *   Weave special features (misconceptions, 21st century skills, etc.) into the core concept flow
    *   PRESERVE all original concept names and terminology from the source PDF

IMPORTANT: Do NOT directly copy large portions of text from the PDF. Instead, use your own words to rewrite and improve the content while maintaining the original concepts and terminology.

**Output Format:**
Provide the complete, rewritten chapter text in Markdown format, incorporating all analyses and image prompts as described. Do not include a preamble or a summary of your analysis; just the final chapter content.
"""
    
    st.info(f"Sending request to Claude via OpenRouter for {grade_level}... This may take some time for larger documents.")
    
    try:
        # Create messages with PDF content
        messages = create_messages_with_pdf_content(prompt_content, pdf_text, pdf_images)
        
        # Make API call
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": YOUR_SITE_URL,
                "X-Title": YOUR_SITE_NAME,
            },
            model=MODEL_NAME,
            messages=messages,
            max_tokens=65536,  # Adjust based on your needs and model limits
            temperature=0.3,
        )
        
        improved_text = completion.choices[0].message.content
        
        return improved_text, "LLM analysis and rewrite complete using Claude via OpenRouter."
        
    except Exception as e:
        st.error(f"Error during OpenRouter API call: {e}")
        return f"Error: Could not complete analysis. {e}", "Error"

def analyze_with_chunked_approach(pdf_file_bytes, pdf_filename, model_progression_text, grade_level):
    """Analyzes the PDF in smaller chunks to handle large documents."""
    st.info("Using chunked approach to analyze PDF...")
    
    try:
        # Extract full text
        doc = fitz.open(stream=pdf_file_bytes, filetype="pdf")
        total_pages = len(doc)
        
        # Determine chunk size
        pages_per_chunk = 5
        
        # Process chunks
        analysis_results = []
        
        for start_page in range(0, total_pages, pages_per_chunk):
            end_page = min(start_page + pages_per_chunk - 1, total_pages - 1)
            st.info(f"Analyzing pages {start_page+1}-{end_page+1} of {total_pages}...")
            
            # Extract text for this chunk
            chunk_text = ""
            chunk_images = []
            
            for page_num in range(start_page, end_page + 1):
                page = doc.load_page(page_num)
                chunk_text += f"\n\n--- Page {page_num + 1} ---\n"
                chunk_text += page.get_text()
                
                # Extract images from this page
                image_list = page.get_images(full=True)
                for img in image_list:  # Include all images from page
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        base64_image = base64.b64encode(image_bytes).decode('utf-8')
                        ext = base_image["ext"]
                        chunk_images.append({
                            "page": page_num + 1,
                            "base64": f"data:image/{ext};base64,{base64_image}",
                        })
                    except:
                        pass
            
            # Analyze this chunk
            chunk_prompt = f"""You are an expert in educational content development for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: You are analyzing CHUNK (Pages {start_page+1}-{end_page+1} of {total_pages}) from a book chapter for **{grade_level} (CBSE)**.
This is just a PORTION of the full chapter - focus only on improving this section according to the model.

The book chapter is intended to align with NCERT, NCF, and NEP 2020 guidelines for **{grade_level}**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

**Target Audience:** {grade_level} (CBSE Syllabus)

**Important Instructions:**
* Rewrite and improve ONLY the content from these pages
* Format like a proper textbook with well-structured paragraphs
* Use clear headings and subheadings where appropriate
* Include Bloom's Taxonomy questions if this section is suitable for them
* Maintain the original concept names/terminology
* Write in your own words - DO NOT copy text directly
* For any images in these pages:
  - Analyze their relevance, clarity, and age-appropriateness
  - Suggest keeping good images or provide image prompts for new/improved ones
  - Image prompts should be marked as: [PROMPT FOR NEW IMAGE: description]

Please provide ONLY the improved version of this specific chunk in Markdown format.
"""
            
            try:
                messages = create_messages_with_pdf_content(chunk_prompt, chunk_text, chunk_images)
                
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": YOUR_SITE_URL,
                        "X-Title": YOUR_SITE_NAME,
                    },
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=32768,
                    temperature=0.3,
                )
                
                improved_chunk = completion.choices[0].message.content
                analysis_results.append(improved_chunk)
                
            except Exception as chunk_e:
                st.warning(f"Error processing chunk: {chunk_e}")
                analysis_results.append(f"[Error processing pages {start_page+1}-{end_page+1}]")
        
        doc.close()
        
        # Combine results
        combined_result = "\n\n".join(analysis_results)
        
        # Final integration
        integration_prompt = f"""You are an expert educational content developer for CBSE curriculum.
You have been given several chunks of rewritten content for a **{grade_level} (CBSE)** book chapter.
Your task is to integrate these chunks into a coherent, well-structured chapter that flows naturally.

This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

**REQUIRED CONTENT STRUCTURE:**
The final integrated chapter MUST follow this specific structure:
1. Current Concepts
2. Hook (with Image Prompt)
3. Learning Outcome
4. Real world connection
5. Previous class concept
6. History
7. Summary
8. Link and Learn based Question
9. Image based question
10. Exercise (with various question types)
11. Skill based Activity
12. Activity Time – STEM
13. Creativity – Art
14. Case Study – Level 1
15. Case Study – Level 2

**Important:**
* Ensure smooth transitions between chunks
* Remove any redundancies
* Create a consistent style and tone
* Format as a proper textbook chapter
* STRICTLY follow the REQUIRED CONTENT STRUCTURE

**Content to integrate:**
{combined_result}

Provide the complete, integrated chapter in Markdown format.
"""
        
        try:
            messages = [{"role": "user", "content": integration_prompt}]
            
            final_completion = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": YOUR_SITE_URL,
                    "X-Title": YOUR_SITE_NAME,
                },
                model=MODEL_NAME,
                messages=messages,
                max_tokens=65536,
                temperature=0.4,
            )
            
            final_improved_text = final_completion.choices[0].message.content
            
            return final_improved_text, "LLM analysis and rewrite complete using chunked approach."
            
        except Exception as integration_e:
            st.error(f"Error during final integration: {integration_e}")
            return combined_result, "Partial analysis complete - final integration failed."
            
    except Exception as e:
        st.error(f"Error during chunked PDF analysis: {e}")
        return f"Error: Could not complete chunked analysis. {e}", "Error"

def create_word_document(improved_text_markdown):
    """Creates a Word document from the improved text (Markdown formatted)."""
    doc = Document()
    
    lines = improved_text_markdown.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line, style='ListBullet')
        else:
            doc.add_paragraph(line)
            
    return doc

# Helper Functions for Content Generation
def create_specific_prompt(content_type, grade_level, model_progression_text, subject_type="Science", word_limits=None):
    """Creates a prompt focused on a specific content type"""
    
    if subject_type == "Mathematics":
        if content_type == "chapter":
            return create_math_chapter_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "exercises":
            return create_math_exercises_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "skills":
            return create_math_skills_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "art":
            return create_math_art_prompt(grade_level, model_progression_text, word_limits)
    elif subject_type == "Mathematics Primary (Classes 1-5)":
        if content_type == "chapter":
            return create_math_primary_chapter_prompt(grade_level, word_limits)
        elif content_type == "exercises":
            return create_math_primary_exercises_prompt(grade_level, word_limits)
        else:
            # For Mathematics Primary, we only support chapter and exercises generation
            return f"""This content type '{content_type}' is not supported for Mathematics Primary (Classes 1-5).
            
For primary mathematics (Classes 1-5), we support:
- Chapter Content: Complete chapter transformation with all components
- Exercises: MCQs, Match the Column, Puzzles, Mental Math, Thinking Activities, and Math Lab Activities

Please use the appropriate generation option."""
    elif subject_type == "Science & E.V.S. (Classes 1-2)":
        # Extract class number to validate
        class_num = grade_level.split()[-1]
        if class_num not in ['1', '2']:
            return "Science & E.V.S. (Classes 1-2) can only be used with Grade 1 or Grade 2."
        
        if content_type == "chapter":
            return create_science_evs_foundational_chapter_prompt(grade_level, word_limits)
        elif content_type == "exercises":
            return create_science_evs_foundational_exercises_prompt(grade_level, word_limits)
        else:
            # For Science EVS Classes 1-2, we only support chapter and exercises (activities) generation
            return f"""This content type '{content_type}' is not supported for Science & E.V.S. (Classes 1-2).
            
For Science & E.V.S. Classes 1-2, we support:
- Chapter Content: Complete play-based chapter transformation
- Activities: Play-based learning activities (not formal exercises)

Please use the appropriate generation option."""
    elif subject_type == "Science & E.V.S. (Classes 3-5)":
        # Extract class number to validate
        class_num = grade_level.split()[-1]
        if class_num not in ['3', '4', '5']:
            return "Science & E.V.S. (Classes 3-5) can only be used with Grade 3, 4, or 5."
        
        if content_type == "chapter":
            return create_science_evs_preparatory_chapter_prompt(grade_level, word_limits)
        elif content_type == "exercises":
            return create_science_evs_preparatory_exercises_prompt(grade_level, word_limits)
        else:
            # For Science EVS Classes 3-5, we only support chapter and exercises generation
            return f"""This content type '{content_type}' is not supported for Science & E.V.S. (Classes 3-5).
            
For Science & E.V.S. Classes 3-5, we support:
- Chapter Content: Complete inquiry-based chapter transformation
- Exercises: Comprehensive assessment exercises

Note: Skills and Art activities are integrated within the chapter content for this subject type.

Please use the appropriate generation option."""
    elif subject_type == "Computer Science":
        if content_type == "chapter":
            return create_computer_chapter_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "exercises":
            return create_computer_exercises_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "skills":
            return create_computer_skills_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "art":
            return create_computer_art_prompt(grade_level, model_progression_text, word_limits)
    else:
        if content_type == "chapter":
            return create_science_chapter_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "exercises":
            return create_science_exercises_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "skills":
            return create_science_skills_prompt(grade_level, model_progression_text, word_limits)
        elif content_type == "art":
            return create_science_art_prompt(grade_level, model_progression_text, word_limits)

# Mathematics Primary Classes (1-5) specific prompt function
def create_math_primary_chapter_prompt(grade_level, word_limits=None):
    """Creates a mathematics-specific chapter content prompt for Classes 1-5 following the lean structure"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'hook': 150,
            'discover': 1500,
            'activity': 300,
            'recap': 200
        }
    
    return f"""You are an Expert Indian Educator and Content Editor specializing in Mathematics textbook transformation for Classes 1-5.

**CRITICAL INSTRUCTIONS**: This prompt is EXCLUSIVELY for Mathematics Classes 1-5. DO NOT apply Model Chapter Progression or any other structure. Follow ONLY the structure specified below.

**Section 0: Prompt Scope and Limitation**
- Specific Application: This is exclusively for transforming Mathematics textbooks for Classes 1 through 5
- Do NOT extend this structure to any other subject or higher grade levels
- This requires a fundamentally different pedagogical approach than secondary education

**Your Role**: Transform the provided PDF chapter into a new, market-leading format using expert pedagogical judgment.

**Target Audience**: {grade_level} (Primary Mathematics - Ages 6-11)

**Three Golden Rules for Transformation**:
1. **PRESERVE THE CORE CONCEPT**: Identify the core mathematical concept(s) and fundamental pedagogical sequence in the PDF
2. **RESTRUCTURE THE LAYOUT**: Completely discard the old layout and use our mandatory four-part lean structure
3. **DETERMINE OPTIMAL LENGTH**: Use expert judgment based on topic complexity (no fixed page limits)

**Guiding Philosophy**:
- **Crystal Clear Language**: Extremely simple, clear language for children aged 6-11
- **Brevity and Impact**: Every page must be purposeful and packed with value
- **Experiential Learning First**: Let children DO or EXPERIENCE the concept
- **CPA Approach**: Concrete-Pictorial-Abstract sequence
- **NEP/NCF Spirit**: Focus on why over how, build thinking skills

**MANDATORY NEW STRUCTURE** (Transform PDF content to fit this EXACT structure):

## 1. Chapter Opener - The Hook (Target: {word_limits.get('hook', 150)} words)
**Action**: Discard any existing opener from PDF. Create completely new content.

**Requirements**:
- Create a captivating full-page illustration description and story
- Set in rich Indian context (Indian names, places, festivals, objects, currency)
- Age-appropriate for 6-11 year olds (positive, encouraging themes)
- Introduce the mathematical concept through story/scenario
- Include detailed image prompt for illustration
- Make it experiential - child should feel connected to the math concept

**Format**:
- Story/scenario that hooks the child
- Visual description for illustration
- Connection to the mathematical concept they'll learn

## 2. Concept & Practice - Let's Discover (Target: {word_limits.get('discover', 1500)} words)
**Action**: Take core lesson from PDF and rewrite completely using CPA approach.

**Requirements**:
- **Variable length**: Just enough pages to cover concept thoroughly without rushing
- **Integrate learning and practice**: Introduce micro-concept, then 2-4 practice questions immediately
- **Replace generic examples**: Use authentic Indian contexts throughout
- **CPA Sequence**: Concrete (manipulatives/real objects) → Pictorial (drawings/images) → Abstract (numbers/symbols)
- **Short sentences**: Break multi-step instructions into numbered points
- **Include "Brain Booster" questions**: Mark with 💡 for Higher Order Thinking Skills
- **Teacher's Notes**: Add "For the Teacher" notes to 70% of content

**Structure for each micro-concept**:
- Simple introduction with concrete example
- Pictorial representation with Indian context
- Abstract mathematical representation
- **2 Concept-wise Examples**: Provide 2 different examples for each concept using Indian context
- **Fun Fact**: Include 1 interesting mathematical fun fact related to each concept
- 2-4 immediate practice questions
- 1 Brain Booster question (💡)

**Content Safety**: Zero bias, show boys and girls equally, diverse representation of India

## 3. Activity Zone - Minds-on, Hands-on (Target: {word_limits.get('activity', 300)} words)
**Action**: Discard any existing activities from PDF. Create completely new content.

**Requirements**:
- **Two fresh activities**: 
  1. **Maths Lab Activity** (tactile, hands-on with real objects)
  2. **Fun with Maths** (game/puzzle format)
- Use easily available materials
- Indian context and examples
- Step-by-step instructions in simple language
- Promote collaboration and positive values
- Age-appropriate for 6-11 year olds

**Format**:
- Activity 1: Maths Lab Activity (hands-on exploration)
- Activity 2: Fun with Maths (engaging game/puzzle)
- Clear materials list
- Step-by-step instructions
- Learning outcome for each activity

## 4. Quick Recap / Revision (Target: {word_limits.get('recap', 200)} words)
**Action**: Create this page from scratch.

**Requirements**:
- **Visual summary**: Mind map or concept map of core concepts from PDF
- **"Let's Revise" section**: 4-5 mixed problems for assessment
- **Simple language**: Child-friendly explanations
- **Indian contexts**: All examples should be culturally relevant
- **Varied question types**: Mix of formats appropriate for the grade level

**Format**:
- Visual concept summary (mind map description)
- "Let's Revise" with 4-5 assessment questions
- Mix of question difficulties
- Answer key or hints

**Content Enhancement Requirements**:
- **Teacher's Notes**: Add practical teaching tips throughout
- **Indian Context**: Replace ALL generic examples with Indian ones (names, places, currency, festivals)
- **Language**: Kind, encouraging, simple voice throughout
- **Safety & Appropriateness**: All content suitable for ages 6-11
- **Inclusivity**: Gender-neutral, culturally diverse, ability-inclusive

**What to Remove from PDF and Replace**:
- Remove: Direct jumps to formulas without conceptual build-up
- Replace: Pages of repetitive drills with varied, contextual problems  
- Replace: Generic or culturally ambiguous examples
- Rewrite: Long, complex paragraphs into short, simple instructions

**Visual Requirements**:
- Include detailed image prompts for illustrations throughout
- Specify Indian cultural elements in visuals
- Ensure age-appropriate, colorful, engaging imagery
- Support the CPA learning progression

Analyze the provided PDF thoroughly and transform it according to this structure. Focus on making mathematics fun, accessible, and meaningful for young Indian children while preserving the core mathematical concepts and learning sequence.

Provide ONLY the transformed mathematics chapter content in Markdown format following the four-part structure above.
"""

def create_math_primary_exercises_prompt(grade_level, word_limits=None):
    """Creates a mathematics-specific exercises prompt for Classes 1-5"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'exercises': 800
        }
    
    return f"""You are an Expert Indian Educator and Content Editor specializing in Mathematics exercises for Classes 1-5.

**CRITICAL INSTRUCTIONS**: This prompt is EXCLUSIVELY for Mathematics Classes 1-5 exercises. Create age-appropriate, engaging mathematical exercises.

**Target Audience**: {grade_level} (Primary Mathematics - Ages 6-11)

Your task is to generate COMPREHENSIVE MATHEMATICS EXERCISES based on the chapter content in the PDF.
**Target Total Word Count for All Exercises**: {word_limits.get('exercises', 800)} words

**REQUIRED EXERCISE TYPES:**

## A. Multiple Choice Questions (MCQs) - 3 Questions
- Create 3 age-appropriate MCQs based on the mathematical concepts
- Use simple language suitable for Classes 1-5
- Include 4 options (A, B, C, D) for each question
- Use Indian context and examples (names, objects, currency)
- Ensure questions test understanding, not just memorization

## B. Match the Column - 5 Pairs
- Create 5 matching pairs related to the mathematical concepts
- Column A: Mathematical concepts, numbers, or problems
- Column B: Corresponding answers, definitions, or examples
- Use visual elements where appropriate (shapes, numbers, objects)
- Include Indian cultural context

## C. Mathematical Puzzle - 1 Puzzle
- Create 1 engaging mathematical puzzle that reinforces the chapter concepts
- Make it fun and challenging but age-appropriate
- Can be number puzzles, pattern puzzles, or logic puzzles
- Include clear instructions and solution approach
- Use colorful, engaging presentation

## D. Mental Math - 3 Questions
- Create 3 mental mathematics questions for quick calculation practice
- Focus on the mathematical concepts from the chapter
- Encourage mental calculation strategies
- Use real-life scenarios familiar to Indian children
- Provide tips for mental calculation where helpful

## E. Thinking Based Activity - 1 Activity
- Create 1 higher-order thinking activity that applies the mathematical concepts
- Encourage problem-solving and critical thinking
- Can involve real-world applications or creative scenarios
- Should promote discussion and multiple solution approaches
- Include guiding questions to support thinking

## F. Math Lab Activity - 1 Activity
- Create 1 hands-on mathematical laboratory activity
- Use easily available materials (household items, simple manipulatives)
- Include step-by-step instructions
- Connect to the mathematical concepts from the chapter
- Promote experiential learning and discovery
- Include observation questions and conclusions

**Content Requirements:**
- **Age-Appropriate Language**: Simple, clear instructions suitable for Classes 1-5
- **Indian Context**: Use Indian names, places, currency, festivals, and cultural elements
- **Visual Elements**: Include descriptions for diagrams, pictures, or visual aids where needed
- **Progressive Difficulty**: Start with easier questions and gradually increase complexity
- **Engaging Content**: Make mathematics fun and interesting for young learners
- **Clear Instructions**: Provide clear, step-by-step instructions for all activities
- **Safety Considerations**: Ensure all activities are safe for young children

**Formatting Requirements:**
- Use clear headings for each exercise type
- Number all questions and activities clearly
- Include answer keys or solution approaches where appropriate
- Use bullet points and numbered lists for clarity
- Mark any materials needed for activities

Ensure that all exercises directly relate to the mathematical concepts covered in the PDF chapter and provide meaningful practice opportunities for young learners.

Provide ONLY the comprehensive mathematics exercises in Markdown format.
"""

# Science & E.V.S. Classes 1-2 (Foundational Stage) specific prompt functions
def create_science_evs_foundational_chapter_prompt(grade_level, word_limits=None):
    """Creates a Science & E.V.S. chapter content prompt for Classes 1-2 following play-based pedagogy"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'opener': 200,
            'activity': 250,
            'concept': 200,
            'closer': 150
        }
    
    # Extract the class number from grade_level (e.g., "Grade 1" -> "1")
    class_num = grade_level.split()[-1]
    if class_num not in ['1', '2']:
        return "This prompt is only for Science & E.V.S. Classes 1-2. Please select Grade 1 or 2."
    
    return f"""You are an ECCE Specialist and Early Years Curriculum Designer.

**CRITICAL INSTRUCTIONS**: This prompt is EXCLUSIVELY for Science & E.V.S. Classes 1-2. DO NOT apply Model Chapter Progression or any other structure. Follow ONLY the Foundational Chapter Blueprint specified below.

**Your Role**: You are an expert in Early Childhood Care and Education (ECCE). Your mission is to create a Science & E.V.S. "activity book" chapter for {grade_level}. This must be joyful, playful, and perfectly aligned with the play-based pedagogy of the NEP 2020 Foundational Stage.

**Target Audience**: {grade_level} (Ages 6-8, Foundational Stage)

**Section 1: The Guiding Philosophy - "Purposeful Play"**
- **Sensory and Experiential**: Learning must happen through seeing, touching, hearing, and doing
- **Story and Rhyme Driven**: All concepts must be introduced through engaging stories, simple rhymes, or captivating oral narratives
- **Visually-Led Learning**: The book must be dominated by large, colourful illustrations. Text for the child is minimal (labels, simple oral questions)
- **Focus on Competencies**: The goal is to develop skills like observation, curiosity, and classification, not the rote learning of facts

**Section 2: The Core Task - The Transformation Engine**
Extract the Core Theme: Identify the single, simple core concept from the PDF (e.g., Water, Plants, Animals)
Architect a Playful Journey: Discard the old structure entirely. Rebuild the chapter using the simplified "Foundational Chapter Blueprint" below. The chapter should be a short, engaging experience, likely 4-6 pages long.

**Section 3: The Foundational Chapter Blueprint (Mandatory Structure)**

## Part 1: Chapter Opener - Story and Wonder (1 Page) (Target: {word_limits.get('opener', 200)} words)
**Action**: The chapter begins one time with this single, immersive page.

**Content**:
- **EeeBee's Introduction 🐝**: Our mascot, EeeBee, welcomes the child to the chapter's topic in a speech bubble
- **Story/Narrative**: A short, simple story for the teacher to read aloud, related to the main illustration
- **Main "Spark" Illustration**: A large, beautiful, full-page illustration
- **Oral "Wonder" Questions**: 2-3 oral discussion questions related to the scene

## The Learning Cycle (Repeated for Each Simple Concept within the Chapter)
After the opener, explore themes by repeating the following two-part cycle for each simple concept:

### Part A of the Cycle: Let's Play & Do (Target: {word_limits.get('activity', 250)} words per activity)
**Action**: A simple, hands-on, game-like activity for the child.
**Instructions**: Pictorial or simple, numbered steps.
**Examples**:
- For "Water": Playing with water in different containers
- For "Plants": Leaf printing activity
- For "Animals": Animal movement game

### Part B of the Cycle: Concept Connect (Target: {word_limits.get('concept', 200)} words per concept)
**Action**: Immediately following the activity, this page elaborates on the learning.
**Content**: 
- A large, central infographic
- A "Read Aloud" explanation for the teacher
- "EeeBee's Takeaway" in a speech bubble to reinforce the concept

## Part 4: Chapter Closer - The 'Learning Together' Corner (1 Page) (Target: {word_limits.get('closer', 150)} words)
**Action**: The chapter concludes one time with this single, consolidated page.

**Content**: Three dedicated sections:
1. **For You! - My Fun Checklist 🌟** (for the student)
   - Simple visual checklist of activities completed
   - Sticker/stamp spaces for achievements
   
2. **For the Teacher - Observation Guide 🧑‍🏫** 
   - Learning Outcomes aligned with NCF
   - Simple observation points
   - Assessment through play suggestions
   
3. **For the Parent - Home Connect 🏠**
   - Simple home activities using everyday materials
   - Questions to ask the child
   - Extension activities for curious learners

**Visual and Language Requirements**:
- **Illustrations**: Large, colorful, child-friendly with Indian contexts
- **Text**: Minimal text for children, mostly labels and speech bubbles
- **Teacher Text**: Clear, simple instructions for read-alouds
- **Safety**: Age-appropriate content with no scary elements
- **Inclusivity**: Diverse representation of Indian children
- **Materials**: Only easily available household items

**Key Differences from Older Classes**:
- NO formal exercises or written work
- NO complex explanations or definitions
- NO abstract concepts without concrete experiences
- Focus on DOING, not memorizing
- Assessment through observation, not testing

Transform the PDF content into this playful, experiential format suitable for young learners.

Provide ONLY the transformed Science & E.V.S. chapter content in Markdown format following the Foundational Chapter Blueprint.
"""

def create_science_evs_foundational_exercises_prompt(grade_level, word_limits=None):
    """Creates a Science & E.V.S. exercises prompt for Classes 1-2 focusing on activities rather than formal exercises"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'activities': 600
        }
    
    # Extract the class number from grade_level
    class_num = grade_level.split()[-1]
    if class_num not in ['1', '2']:
        return "This prompt is only for Science & E.V.S. Classes 1-2. Please select Grade 1 or 2."
    
    return f"""You are an ECCE Specialist and Early Years Curriculum Designer.

**CRITICAL INSTRUCTIONS**: This prompt is EXCLUSIVELY for Science & E.V.S. Classes 1-2 activities. Create age-appropriate, play-based learning activities, NOT formal exercises.

**Target Audience**: {grade_level} (Ages 6-8, Foundational Stage)

Your task is to generate PLAY-BASED LEARNING ACTIVITIES based on the chapter content in the PDF.
**Target Total Word Count for All Activities**: {word_limits.get('activities', 600)} words

**REQUIRED ACTIVITY TYPES:**

## A. Observation Activities - 2 Activities
- Simple observation tasks using the five senses
- Draw and color activities
- Spot the difference or find the object activities
- Use large, clear illustrations

## B. Sorting and Classifying Games - 1 Activity
- Sort objects by color, size, shape, or type
- Group living/non-living things
- Match parent and baby animals
- Use picture cards or real objects

## C. Story-Based Activities - 1 Activity
- Complete a simple story with pictures
- Sequence story cards in order
- Act out a story with movements
- Create sound effects for a story

## D. Nature Walk Activity - 1 Activity
- Guided outdoor exploration
- Simple collection activities (leaves, stones)
- Observation checklist with pictures
- Safety rules clearly stated

## E. Art and Craft - 1 Activity
- Simple craft using natural materials
- Finger painting or hand printing
- Making simple models with clay
- Creating patterns with shapes

## F. Circle Time Games - 2 Activities
- Movement games related to the concept
- Simple songs or rhymes with actions
- Show and tell activities
- Group discussion prompts

**Activity Requirements**:
- **Picture-Based Instructions**: Use mostly pictures with minimal text
- **Safety First**: All activities must be completely safe for young children
- **Adult Supervision**: Clearly indicate when adult help is needed
- **Indian Context**: Use familiar Indian contexts and materials
- **Inclusive**: Ensure all children can participate regardless of ability
- **Fun Focus**: Make every activity enjoyable and engaging
- **No Writing**: Activities should not require writing skills

**Format for Each Activity**:
- Activity name with fun emoji
- What you need (with pictures)
- How to play (step-by-step with illustrations)
- What to observe/discover
- Extension ideas for home

Remember: These are NOT exercises but joyful learning experiences. Focus on exploration, discovery, and play.

Provide ONLY the play-based learning activities in Markdown format.
"""

# Science & E.V.S. Classes 3-5 (Preparatory Stage) specific prompt functions  
def create_science_evs_preparatory_chapter_prompt(grade_level, word_limits=None):
    """Creates a Science & E.V.S. chapter content prompt for Classes 3-5 following inquiry-based approach"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'opener': 300,
            'exploration': 2000,
            'project': 400,
            'summary': 250,
            'exercises': 600
        }
    
    # Extract the class number from grade_level
    class_num = grade_level.split()[-1]
    if class_num not in ['3', '4', '5']:
        return "This prompt is only for Science & E.V.S. Classes 3-5. Please select Grade 3, 4, or 5."
    
    return f"""You are a Master Educator and Curriculum Architect specializing in Indian primary education.

**CRITICAL INSTRUCTIONS**: This prompt is EXCLUSIVELY for Science & E.V.S. Classes 3-5. DO NOT apply standard Model Chapter Progression. Follow ONLY the Final Chapter Blueprint specified below.

**Your Role**: You are a visionary curriculum designer creating Science & E.V.S. textbooks for {grade_level} that are pedagogically advanced, with a comprehensive and engaging assessment structure that ensures concept mastery and sets a new market standard.

**Target Audience**: {grade_level} (Ages 8-11, Preparatory Stage)

**Section 1: The Guiding Philosophy - "Inquiry with Clarity"**
- **The Core Mission**: Create dynamic chapters where the student discovers through doing. The book is a guide for exploration, with a clear focus on building scientific process skills
- **Principle of Balanced Dynamism**: Primary focus on clear communication of core concepts. 'Monotony-Breaker' elements and inline questions must support and enrich, never clutter or distract
- **Activity-Led Explanation**: The hands-on activity is the catalyst for the explanation. Students must DO first, then learn the theory

**Section 2: The Core Task - The Transformation Engine**
1. **Determine Subject Title**: Analyze the source PDF to determine if it's EVS or Science
2. **Extract the Skeleton**: Identify every core concept and sub-concept. None should be omitted
3. **Architect the New Body**: Rebuild using the Final Chapter Blueprint below
4. **Determine Optimal Content Depth**: Explanations must be well-structured, elaborative paragraphs

**Section 3: The Final Chapter Blueprint (Mandatory Structure)**

## Part 1: The Chapter Opener Page (1 Page) (Target: {word_limits.get('opener', 300)} words)
- **The "Learning Roadmap" with EeeBee 🐝**:
  * Previous Knowledge Connections
  * Learning Outcomes (clear, measurable)
  * NCF Learning Goals alignment
- **The "Spark Illustration"**: Captivating visual related to the chapter theme
- **"Let's Wonder..." Questions**: 3-4 thought-provoking questions to spark curiosity

## Part 2: The Exploration - "Let's Uncover the Secrets" (Variable Pages) (Target: {word_limits.get('exploration', 2000)} words)
**Structure**: Break down the main topic into logical sub-parts, mirroring the source material.

**Content Flow for Each Sub-part**:
1. **Quick In-Class Activity** or intriguing question to introduce the sub-part
2. **Detailed Explanation** in elaborative paragraphs:
   - Clear, age-appropriate language
   - Step-by-step concept building
   - Real-world connections
3. **Strategic Integration of Monotony-Breakers**:
   - [Amazing Fact! 🌟]: Fascinating facts related to the concept
   - [Think & Talk 💭]: Discussion prompts for peer learning
   - [Misconception Alert! ⚠️]: Common errors to avoid
   - [Science Story Time 📖]: Brief narratives connecting to the concept
   - [Quick Quiz Corner 🎯]: Single MCQ for immediate assessment
4. **Checkpoint: What We Just Learnt**: Bullet-point summary box
5. **Science Around You**: Real-life applications box

## Part 3: The Chapter Capstone Project (1-2 Pages) (Target: {word_limits.get('project', 400)} words)
**Action**: A mandatory, culminating project synthesizing chapter learning.

**Types**:
- Detailed experiment with materials, procedure, observations
- Model making with step-by-step instructions
- Research-based chart/poster presentation
- Field observation project

**Structure**:
- Project Title and Objective
- Materials Required (easily available)
- Step-by-Step Procedure
- Observation Sheet/Recording Format
- Conclusion Questions
- Presentation Guidelines

## Part 4: Chapter Summary & Revision Tools (1 Page) (Target: {word_limits.get('summary', 250)} words)
**Content**:
- **In a Nutshell**: Bulleted summary of key concepts
- **Key Words / Word Lab**: Glossary of new scientific terms
- **Concept Map**: Visual diagram showing relationships between concepts
- **Quick Revision Questions**: 5-6 rapid-fire questions

## Part 5: Comprehensive End-of-Chapter Exercise (1-2 Pages) (Target: {word_limits.get('exercises', 600)} words)
**Section A: Remembering & Understanding**
- Fill in the Blanks (5 questions)
- True/False with Corrections (5 questions)
- MCQs (5 questions)
- Name the Following (5 items)
- Match the Column (5 pairs)

**Section B: Application, Analysis & Evaluation**
- Give Reasons (3 questions)
- Differentiate Between (2 pairs)
- Answer in Brief (3 questions)
- Answer in Detail (2 questions)
- HOTS/Pondering Questions (2 questions)

**Content Requirements**:
- **Age-Appropriate Complexity**: Match depth to {grade_level} cognitive abilities
- **Indian Context**: Use Indian examples, names, places, scenarios
- **Scientific Accuracy**: Ensure all content is scientifically correct
- **Process Skills Focus**: Emphasize observation, classification, inference
- **Environmental Awareness**: Include eco-friendly practices
- **Health & Safety**: Integrate health consciousness where relevant

**Quality Control**:
- Simple, clear language appropriate for {grade_level}
- Gender-inclusive and culturally sensitive
- Urban and rural balance in examples
- Emphasis on hands-on learning
- Integration of values and life skills

Transform the PDF content into this inquiry-based format that makes science exciting and accessible.

Provide ONLY the transformed Science & E.V.S. chapter content in Markdown format following the Final Chapter Blueprint.
"""

def create_science_evs_preparatory_exercises_prompt(grade_level, word_limits=None):
    """Creates a Science & E.V.S. exercises prompt for Classes 3-5 with comprehensive assessment"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'exercises': 800
        }
    
    # Extract the class number from grade_level
    class_num = grade_level.split()[-1]
    if class_num not in ['3', '4', '5']:
        return "This prompt is only for Science & E.V.S. Classes 3-5. Please select Grade 3, 4, or 5."
    
    return f"""You are a Master Educator and Curriculum Architect specializing in Indian primary education.

**CRITICAL INSTRUCTIONS**: This prompt is EXCLUSIVELY for Science & E.V.S. Classes 3-5 exercises. Create comprehensive, inquiry-based assessment exercises.

**Target Audience**: {grade_level} (Ages 8-11, Preparatory Stage)

Your task is to generate COMPREHENSIVE SCIENCE & E.V.S. EXERCISES based on the chapter content in the PDF.
**Target Total Word Count for All Exercises**: {word_limits.get('exercises', 800)} words

**REQUIRED EXERCISE STRUCTURE:**

## Section A: Remembering & Understanding

### 1. Fill in the Blanks - 5 Questions
- Test key vocabulary and concepts
- Use scientific terms from the chapter
- Progress from simple to complex

### 2. True/False with Corrections - 5 Questions
- Include common misconceptions
- Require students to correct false statements
- Test conceptual understanding

### 3. Multiple Choice Questions (MCQs) - 5 Questions
- Include 4 options (a, b, c, d) for each
- Test various cognitive levels
- Include diagram-based questions where relevant

### 4. Name the Following - 5 Items
- Quick recall questions
- Include examples, definitions, and identifications
- Cover all major concepts from the chapter

### 5. Match the Column - 5 Pairs
- Column A: Terms/Concepts
- Column B: Definitions/Examples
- Ensure logical connections

## Section B: Application, Analysis & Evaluation

### 1. Give Reasons - 3 Questions
- "Why" questions requiring scientific explanation
- Test cause-effect understanding
- Encourage logical thinking

### 2. Differentiate Between - 2 Pairs
- Compare and contrast related concepts
- Use tabular format for answers
- Test deeper understanding

### 3. Answer in Brief - 3 Questions
- 2-3 sentence answers expected
- Test application of concepts
- Include real-world scenarios

### 4. Answer in Detail - 2 Questions
- 5-6 sentence answers expected
- Comprehensive understanding required
- May include diagram drawing

### 5. HOTS (Higher Order Thinking Skills) - 2 Questions
- Open-ended, thought-provoking questions
- Encourage critical thinking
- Connect to real-world problems

## Additional Components:

### Activity-Based Questions - 2 Questions
- Based on experiments/activities in the chapter
- Test procedural knowledge
- Include observation and inference

### Diagram-Based Questions - 2 Questions
- Label the diagram
- Draw and explain
- Interpret given diagrams

### Value-Based Questions - 1 Question
- Connect science to daily life values
- Environmental consciousness
- Social responsibility

**Question Design Principles**:
- **Progressive Difficulty**: Start simple, increase complexity
- **Comprehensive Coverage**: Address all chapter concepts
- **Clear Language**: Age-appropriate vocabulary
- **Indian Context**: Use local examples and scenarios
- **Visual Elements**: Include diagrams where helpful
- **Life Skills Integration**: Connect to practical applications

**Assessment Objectives**:
- Test factual knowledge and conceptual understanding
- Develop scientific reasoning
- Encourage observation and inference skills
- Build environmental awareness
- Foster scientific temper

Ensure all questions are directly related to the chapter content and appropriate for {grade_level} students.

Provide ONLY the comprehensive Science & E.V.S. exercises in Markdown format.
"""

# Mathematics-specific prompt functions
def create_math_chapter_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a mathematics-specific chapter content prompt"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'hook': 70,
            'learning_outcome': 70,
            'real_world': 50,
            'previous_class': 100,
            'history': 100,
            'current_concepts': 4000,
            'summary': 700,
            'link_learn': 250,
            'image_based': 250
        }
    
    return f"""You are an expert in mathematical education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes.

You are analyzing a mathematics book chapter intended for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines for Mathematics education.

**CRITICAL INSTRUCTION**: The PDF may contain MULTIPLE MAJOR SECTIONS (e.g., Section 1, Section 2, Section 3, etc.). You MUST include ALL sections present in the PDF. Do NOT stop after completing just one or two sections. Generate comprehensive content for EVERY section found in the document.

**Model Chapter Progression and Elements (Base Structure):**
---
{model_progression_text}
---

**Target Audience:** {grade_level} (CBSE Mathematics Syllabus)

Your task is to generate COMPREHENSIVE MATHEMATICS CHAPTER CONTENT following the Model Chapter Progression structure enhanced with mathematics-specific elements.

**IMPORTANT**: If the PDF contains multiple sections (e.g., "Section 2: Place Value", "Section 3: Operations and Estimation with Large Numbers"), you MUST generate complete content for EACH section. The structure below should be applied to EACH major section in the PDF.

**REQUIRED SECTIONS (Generate ALL with substantial content for EACH major section in the PDF):**

## I. Chapter Opener

1. **Chapter Title** - Engaging and mathematically focused

2. **Hook (with Image Prompt)** (Target: {word_limits.get('hook', 80)} words)
   - Create an engaging mathematical opening that captures student interest
   - Use real-life mathematical scenarios, surprising mathematical facts, or thought-provoking mathematical questions
   - Connect to students' daily mathematical experiences
   - Include a detailed image prompt for a compelling mathematical visual

3. **Real-World Connection** (Target: {word_limits.get('real_world', 100)} words)
   - Provide multiple real-world applications of the mathematical concepts
   - Show how math is used in everyday life situations
   - Include examples from technology, engineering, finance, science, etc.
   - Connect to mathematical careers and future studies

4. **Learning Outcomes** (Target: {word_limits.get('learning_outcome', 125)} words)
   - List specific, measurable mathematical learning objectives
   - Use action verbs (define, explain, calculate, apply, analyze, solve, prove, etc.)
   - Align with Bloom's Taxonomy levels for mathematics
   - Connect to CBSE mathematics curriculum standards

5. **Previous Class Link** (Target: {word_limits.get('previous_class', 100)} words)
   - Link to prior mathematical knowledge from previous classes
   - Explain how previous concepts connect to current learning
   - Provide a brief review of essential prerequisites

6. **Chapter Map/Overview** (Target: {word_limits.get('summary', 100)} words)
   - Visual layout of mathematical concepts (mind map or flowchart description)
   - Show mathematical progressions and connections

7. **Meet the Character (EeeBee)** (Target: 50-100 words)
   - Introduce EeeBee as a mathematical guide/helper throughout the chapter

## II. Core Content Sections (REPEAT FOR EACH MAJOR SECTION IN THE PDF)

**NOTE: If the PDF has Section 1, Section 2, Section 3, etc., create complete content for EACH section following this structure:**

8. **Introduction of Section** (Target: 100 words)
   - Give a related section introduction that sets the mathematical context
   - Explain the importance of the mathematical concepts to be learned
   - Connect to the broader mathematical curriculum

9. **History of the chapter** (Target: 150 words)
   - Provide comprehensive historical background of the chapter
   - Include key mathematicians, their contributions, and discoveries
   - Explain the timeline of mathematical developments
   - Explain the history of the chapter

10. **Warm-up Questions** (Target: {word_limits.get('previous_class', 100)} words)
    - Create 5-7 engaging warm-up questions that connect to prior mathematical knowledge
    - Include a mix of question types (mental math, real-world problems, pattern recognition)

11. **Current Concepts** (Target: {word_limits.get('current_concepts', 4000)} words per section)
    
    For each major concept in EACH section, include ALL of the following:
    
    **A. Concept Introduction** (Target: 120 words per concept)
    - Clear introduction to each mathematical concept
    - Simple, clear mathematical language
    - Use analogies and mathematical examples
    - Identify all subconcepts that will be covered under this main concept
    
    **B. Subconcepts (As per NCERT Books)** (Target: 200 words per concept)
    - **IMPORTANT**: Identify and include ALL subconcepts present in NCERT books for this topic
    - Each main concept typically has 2-5 subconcepts in NCERT mathematics books
    - Subconcepts should be clearly labeled and integrated within the main concept
    - Examples of subconcepts:
      * For "Fractions": Types of fractions, Equivalent fractions, Comparing fractions, etc.
      * For "Triangles": Types of triangles, Properties of triangles, Congruence, etc.
      * For "Integers": Positive and negative integers, Operations on integers, Properties, etc.
    - Each subconcept should include:
      * Definition and explanation 
      * Examples and illustrations
      * Key points to remember
      * Common errors to avoid
    
    **C. Mathematical Explanation** (Target: 450 words per concept)
    - Detailed theoretical understanding of the mathematical concept and its subconcepts
    - Include step-by-step mathematical reasoning and derivations
    - Show different mathematical approaches where applicable
    - Ensure each subconcept is thoroughly explained with connections to the main concept
    
    **D. Solved Examples** (Target: 550 words per concept)
    - Provide 4-5 different worked examples for each concept
    - Include examples that cover different subconcepts
    - Include step-by-step solutions with clear explanations
    - Use varied difficulty levels and question formats
    - Ensure examples demonstrate application of all subconcepts
    
    **E. Concept-Based Exercise Questions** (Target: 450 words per concept)
    Create the following specific mathematical question types for each concept:
    
    1. **Fill in the Blanks** - 3-4 questions
       - Mathematical formulas, definitions, and key concept completion
    
    2. **Conversion-Based Questions** - 2 questions
       - Unit conversions, mathematical transformations
    
    3. **Word Problems (Real-life Context)** - 5 questions
       - Real-world mathematical scenarios applying the concept
       - Varied difficulty levels from basic to complex applications
    
    4. **Match the Columns** - 1 question (5 matches)
       - Mathematical concepts with definitions, formulas with applications
    
    5. **Estimation Questions (Real-life Estimation)** - 5 questions
       - Practical mathematical estimation scenarios
       - Real-world mathematical approximation problems
    
    6. **Miscellaneous Questions** - 3 questions
       - Mixed question types testing various aspects of the concept
       - Include higher-order thinking and application problems
    
    **F. Visuals** (Throughout each concept)
    - Include detailed image prompts for mathematical diagrams, graphs, and illustrations
    
    **G. Mathematical Activities/Experiments** (Target: 220 words per concept)
    - Step-by-step mathematical experiments or investigations
    - Inquiry-based mathematical activities
    
    **H. Check Your Understanding** (Target: 170 words per concept)
    - Quick check questions (2-3 simple questions) to test immediate understanding
    - Brief conceptual questions or simple calculations
    
    **I. Key Mathematical Terms** (Target: 120 words per concept)
    - Highlighted mathematical terminology in text
    - Clear mathematical definitions
    
    **J. Mathematical Applications** (Target: 220 words per concept)
    - Show relevance to daily life, mathematical careers, technology
    
    **K. Fun Mathematical Facts** (Target: 120 words per concept)
    - Include interesting mathematical facts related to the concept
    
    **L. Think About It! (Mathematical Exploration)** (Target: 120 words per concept)
    - Present thought-provoking mathematical questions or scenarios
    
    **M. Mental Mathematics** (Target: 170 words per concept)
    - Provide mental mathematics strategies and techniques

## III. Special Features (Apply to the ENTIRE chapter, not just one section)

12. **Common Mathematical Misconceptions** (Target: 250 words)
    - 2-3 misconceptions per mathematical concept
    - Correct early mathematical misunderstandings

13. **21st Century Skills Focus** (Target: {word_limits.get('skill_activity', 350)} words)
    - Mathematical Design Challenge
    - Mathematical Debate
    - Collaborate & Create

14. **Differentiation** (Target: {word_limits.get('exercises', 250)} words)
    - Challenge sections for advanced mathematical learners
    - Support sections for mathematical revision

15. **Technology Integration** (Target: {word_limits.get('stem_activity', 180)} words)
    - Mathematical software and tools
    - Digital mathematical simulations

16. **Character Integration** (Throughout)
    - EeeBee appears throughout to ask mathematical questions

## IV. Chapter Wrap-Up (For the ENTIRE chapter)

17. **Self-Assessment Checklist** (Target: {word_limits.get('exercises', 220)} words)
    - Create a comprehensive self-assessment checklist

18. **Chapter-wise Miscellaneous Exercise** (Target: {word_limits.get('exercises', 550)} words)
    - MCQs (5 questions)
    - Short/Long Answer (3 short, 2 long)
    - Open-ended Mathematical Problems (2 questions)
    - Assertion & Reason (3 statements)
    - Mathematical Concept Mapping (1 map)
    - True/False with Justification (5 statements)
    - Mathematical Case Studies (1 scenario)
    - Mathematical Puzzle (1 puzzle)
    - Thinking Based Activities

19. **Apply Your Mathematical Knowledge** (Target: {word_limits.get('skill_activity', 280)} words)
    - Real-world mathematical application tasks
    - Project-based mathematical problems

**CONTENT REQUIREMENTS:**
* **CRITICAL**: Include ALL major sections from the PDF (e.g., if there are Sections 1, 2, and 3, generate complete content for ALL three)
* **Mathematical Accuracy**: Ensure all mathematical content is accurate
* **Clear Mathematical Language**: Use precise mathematical terminology
* **Step-by-step Solutions**: Provide detailed mathematical working
* **Visual Integration**: Include detailed image prompts
* **Progressive Difficulty**: Structure content from basic to advanced
* DO NOT use the same mathematical figures (numbers) from the pdf

Provide ONLY the comprehensive mathematics chapter content in Markdown format. Remember to include EVERY section found in the PDF document.
"""

def create_math_exercises_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a mathematics-specific exercises prompt with dynamic word limits"""
    if word_limits is None:
        word_limits = {
            'exercises': 800
        }
    return f"""You are an expert in mathematical education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a mathematics book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate COMPREHENSIVE MATHEMATICS EXERCISES based on the chapter content in the PDF.
**Target Total Word Count for All Exercises**: {word_limits.get('exercises', 800)} words

**Core Mathematical Exercise Types:**
1. **MCQ (Multiple Choice Questions)** - at least 12 questions with detailed solutions
2. **Short Answer Mathematical Problems** - at least 8 questions  
3. **Long Answer Mathematical Problems** - at least 5 questions
4. **Assertion & Reason (Mathematical)** - at least 5 questions
5. **True/False with Mathematical Justification** - at least 10 statements
6. **Fill in the Blanks (Mathematical)** - at least 10 questions
7. **Match the Following (Mathematical)** - at least 2 sets with 5 matches each
8. **Mathematical Concept Mapping** - at least 1 comprehensive exercise
9. **Mathematical Case Studies** - at least 2 scenarios
10. **Open-ended Mathematical Problems** - at least 3 questions

**Special Mathematical Features:**
- **EeeBee Integration**: Include questions where EeeBee guides mathematical thinking
- **Technology Integration**: Questions involving mathematical software, calculators, or digital tools
- **Differentiation**: Include challenge problems for advanced learners and support questions for revision
- **21st Century Skills**: Collaborative mathematical problems and communication-based questions

Ensure that:
* Questions cover ALL important mathematical concepts from the PDF
* Questions follow Bloom's Taxonomy at various levels
* Mathematical language is clear and appropriate for {grade_level}
* Questions increase in difficulty progressively
* All exercises include detailed mathematical solutions with step-by-step working
* Content is formatted in Markdown with proper mathematical notation

Provide ONLY the comprehensive mathematical exercises in Markdown format.
"""

def create_math_skills_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a mathematics-specific skills and STEM activities prompt with dynamic word limits"""
    if word_limits is None:
        word_limits = {
            'skill_activity': 400,
            'stem_activity': 400
        }
    return f"""You are an expert in mathematical education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a mathematics book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate MATHEMATICAL SKILL-BASED ACTIVITIES and STEM projects.

## Mathematical Skill-Based Activities (Target: {word_limits.get('skill_activity', 400)} words)

Create at least 3 comprehensive mathematical activities:

**Activity Structure for Each:**
1. **Clear Mathematical Objective**
2. **Materials Required**
3. **Step-by-Step Mathematical Procedure**
4. **Inquiry-Based Mathematical Exploration**
5. **Real-Life Mathematical Connections**
6. **EeeBee Integration**
7. **Mathematical Reflection Questions**
8. **Expected Mathematical Outcomes**

**Types of Mathematical Activities:**
- Mathematical Experiments/Investigations
- Mathematical Manipulative Activities
- Mathematical Problem-Solving Challenges
- Mathematical Pattern Recognition Activities
- Mathematical Measurement and Data Collection

## Mathematical STEM Projects (Target: {word_limits.get('stem_activity', 400)} words)

Create at least 2 comprehensive projects that integrate mathematics with Science, Technology, and Engineering:

**Project Structure for Each:**
1. **Mathematical Integration Focus**
2. **Real-World Mathematical Application**
3. **Technology Integration**
4. **Collaborative Mathematical Work**
5. **Mathematical Design Challenge**
6. **Mathematical Analysis and Calculations**
7. **Mathematical Presentation Component**
8. **Assessment Criteria**

**STEM Integration Examples:**
- Mathematical Modeling in Science
- Engineering Design with Mathematical Constraints
- Technology-Enhanced Mathematical Problem Solving
- Mathematical Data Analysis Projects

Format the content in Markdown with proper mathematical notation.

Provide ONLY the Mathematical Skill Activities and STEM Projects in Markdown format.
"""

def create_math_art_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a mathematics-specific art integration prompt with dynamic word limits"""
    if word_limits is None:
        word_limits = {
            'art_learning': 400
        }
    return f"""You are an expert in mathematical education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a mathematics book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate MATHEMATICS-INTEGRATED CREATIVE LEARNING projects.
**Target Total Word Count for All Art-Integrated Learning**: {word_limits.get('art_learning', 400)} words

## Mathematical Art Projects

Create at least 3 creative projects that connect mathematical concepts to various art forms:

**Project Structure for Each:**
1. **Mathematical Learning Objective**
2. **Art Form Integration**
3. **Mathematical Concepts Highlighted**
4. **Materials and Tools**
5. **Step-by-Step Mathematical-Artistic Process**
6. **EeeBee's Creative Guidance**
7. **Mathematical Reflection and Analysis**
8. **Showcase and Communication**

**Types of Mathematical Art Integration:**
- Geometric Art and Patterns
- Mathematical Music and Rhythm
- Mathematical Drama and Storytelling
- Mathematical Digital Art
- Mathematical Sculpture and 3D Models

## Mathematical Case Studies

**Case Study – Level 1 (Accessible Mathematical Analysis):**
Create at least 1 simpler case study that:
- Presents a real-world mathematical scenario appropriate for {grade_level}
- Includes guided mathematical analysis questions
- Is accessible to all students with basic mathematical skills

**Case Study – Level 2 (Advanced Mathematical Challenge):**
Create at least 1 more complex case study that:
- Challenges students with multi-step mathematical problems
- Requires deeper application of mathematical concepts
- Encourages higher-order mathematical thinking skills

**Case Study Structure for Each:**
1. **Real-World Mathematical Context**
2. **Mathematical Background Information**
3. **Guided Mathematical Questions**
4. **Mathematical Analysis Requirements**
5. **Creative Mathematical Solutions**
6. **Mathematical Communication Component**
7. **EeeBee's Mathematical Insights**
8. **Extension Mathematical Challenges**

Format the content in Markdown with proper mathematical notation.

Provide ONLY the Mathematics-Integrated Creative Learning content in Markdown format.
"""

# Science subject prompt functions
def create_science_chapter_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a science subject chapter content prompt with dynamic word limits"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'hook': 70,
            'learning_outcome': 70,
            'real_world': 50,
            'previous_class': 100,
            'history': 100,
            'current_concepts': 1200,
            'summary': 700,
            'link_learn': 250,
            'image_based': 250,
            'exercises': 800,
            'skill_activity': 400,
            'stem_activity': 400,
            'art_learning': 400
        }
    
    return f"""You are an expert in science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes.

You are analyzing a science book chapter intended for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines for Science education.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

**Target Audience:** {grade_level} (CBSE Science Syllabus)

Your task is to generate COMPREHENSIVE CORE SCIENCE CHAPTER CONTENT that should be equivalent to a complete science textbook chapter.

**REQUIRED SECTIONS (Generate ALL with substantial content):**

1. **Current Concepts** (Target: {word_limits.get('current_concepts', 1200)} words)
   
   For each major scientific concept in the chapter, include ALL of the following:
   
   **A. Concept Introduction** (Target: 120 words per concept)
   - Clear introduction to each scientific concept
   - Simple, clear scientific language
   - Use analogies and real-world scientific examples
   - Identify all subconcepts that will be covered under this main concept
   
   **B. Subconcepts (As per NCERT Science Books)** (Target: 500 - 600 words per concept)
   - **IMPORTANT**: Identify and include ALL subconcepts present in NCERT science books for this topic
   - Each main concept typically has 2-5 subconcepts in NCERT science books
   - Subconcepts should be clearly labeled and integrated within the main concept
   - Examples of subconcepts:
     * For "Matter": States of matter, Properties of matter, Changes of state, etc.
     * For "Light": Reflection, Refraction, Dispersion, etc.
     * For "Cell": Plant cells, Animal cells, Cell organelles, Cell division, etc.
   - Each subconcept should include:
     * Definition and explanation 
     * Scientific examples and illustrations
     * Key scientific points to remember
     * Common scientific errors to avoid
   
   **C. Scientific Explanation** (Target: 450 words per concept)
   - Detailed theoretical understanding of the scientific concept and its subconcepts
   - Include step-by-step scientific reasoning and explanations
   - Show different scientific approaches where applicable
   - Ensure each subconcept is thoroughly explained with connections to the main concept
   
   **D. Scientific Examples and Applications** (Target: 350 words per concept)
   - Provide 4-5 different real-world examples for each concept
   - Include examples that cover different subconcepts
   - Include step-by-step explanations with clear scientific reasoning
   - Use varied complexity levels and application formats
   - Ensure examples demonstrate application of all subconcepts
   
   **E. Concept-Based Questions** (Target: 300 words per concept)
   - Give questions for each current concept - 3 MCQs, 2 Short questions, 1 Long question
   - Questions should test different subconcepts
   - Include scientific reasoning and application-based questions
   
   **F. Scientific Activity** (Target: 200 words per concept)
   - Give scientific activity according to the concept
   - Step-by-step scientific experiments or investigations
   - Inquiry-based scientific activities
   
   **G. Scientific Facts and Applications** (Target: 150 words per concept)
   - Give fun scientific fact for each concept
   - Show relevance to daily life, scientific careers, technology
   - Connect to current scientific research and discoveries
   
   **H. Key Scientific Points** (Target: 120 words per concept)
   - Give key scientific points for each concept
   - Highlighted scientific terminology and definitions
   - Essential scientific principles and formulas
   
   **I. Common Scientific Misconceptions** (Target: 150 words per concept)
   - Give common scientific misconceptions for each concept
   - Correct early scientific misunderstandings
   - Explain why these misconceptions occur
   
   **J. Visual Integration** (Throughout each concept)
   - Include detailed image prompts for scientific diagrams, experiments, and illustrations
   
   - Mark concepts which are exactly coming from the PDF and give some extra concepts for higher level understanding
   - Make sure there is no repetition of concepts

2. **Hook (with Image Prompt)** (Target: {word_limits.get('hook', 80)} words)
   - Create an engaging scientific opening that captures student interest
   - Use scientific storytelling, surprising scientific facts, or thought-provoking scientific questions
   - Connect to students' daily scientific experiences or current scientific events
   - Include a detailed image prompt for a compelling scientific visual

3. **Learning Outcome** (Target: {word_limits.get('learning_outcome', 70)} words)
   - List specific, measurable scientific learning objectives
   - Use action verbs (analyze, evaluate, create, experiment, investigate, etc.)
   - Align with Bloom's Taxonomy levels for science education
   - Connect to CBSE science curriculum standards

4. **Real World Connection** (Target: {word_limits.get('real_world', 50)} words)
   - Provide multiple real-world applications of the scientific concepts
   - Include current examples from technology, environment, health, space science, etc.
   - Explain how the scientific concepts impact daily life
   - Connect to scientific careers and future studies

5. **Previous Class Concept** (Target: {word_limits.get('previous_class', 100)} words)
   - Give the scientific concept name and the previous class it was studied in according to NCERT science textbooks
   - Link to prior scientific knowledge and foundations

6. **History** (Target: {word_limits.get('history', 100)} words)
   - Provide comprehensive historical background of scientific discoveries
   - Include key scientists, inventors, or scientific figures and their contributions
   - Explain the timeline of scientific developments and discoveries
   - Connect historical scientific context to modern understanding

7. **Summary** (Target: {word_limits.get('summary', 700)} words)
   - Create detailed concept-wise scientific summaries (not just one overall summary)
   - Include key scientific points, formulas, and important scientific facts
   - Organize by individual scientific concepts covered in the chapter
   - Provide clear, concise explanations that reinforce scientific learning

8. **Link and Learn Based Question** (Target: {word_limits.get('link_learn', 250)} words)
   - Create 3-5 questions that connect different scientific concepts
   - Include questions that link to other science subjects or real-world scientific scenarios
   - Provide detailed explanations for the scientific connections

9. **Image Based Question** (Target: {word_limits.get('image_based', 250)} words)
   - Create 3-5 questions based on scientific images/diagrams from the chapter
   - Include detailed scientific image descriptions if creating new image prompts
   - Ensure questions test scientific understanding, not just observation

**CONTENT REQUIREMENTS:**
* **Scientific Accuracy**: Ensure all scientific content is accurate and up-to-date
* **Detailed Scientific Explanations**: Each scientific concept should be explained thoroughly with multiple paragraphs
* **Scientific Examples and Illustrations**: Include numerous scientific examples, case studies, and practical applications
* **Age-Appropriate Scientific Language**: Use scientific vocabulary suitable for {grade_level} but don't oversimplify
* **Engaging Scientific Tone**: Write in an engaging, conversational style that maintains student interest in science
* **Clear Scientific Structure**: Use proper headings, subheadings, and formatting for science content
* **Visual Integration**: Include detailed image prompts for scientific diagrams, experiments, and illustrations

**FORMATTING REQUIREMENTS:**
* Use Markdown formatting with clear headings (# ## ###)
* Include bullet points and numbered lists where appropriate for scientific content
* Use **bold** for key scientific terms and *italics* for emphasis
* Create well-structured paragraphs (3-5 sentences each) explaining scientific concepts
* Include image prompts marked as: [PROMPT FOR NEW IMAGE: detailed scientific description]

**SCIENTIFIC QUALITY STANDARDS:**
* Each section should be scientifically substantial and comprehensive
* Avoid superficial coverage - go deep into each scientific topic
* Include multiple scientific perspectives and approaches to concepts
* Ensure content flows logically from one scientific concept to the next
* Maintain consistency in scientific terminology and explanations
* Connect scientific concepts to real-world applications and current scientific research
* Include age-appropriate scientific investigations and inquiry-based learning

Analyze the PDF document thoroughly and create improved scientific content that expands significantly on what's provided while maintaining all original concept names and terminology.

Provide ONLY the comprehensive science chapter content in Markdown format. Do not include exercises, activities, or art projects.
"""

def create_science_exercises_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a science subject exercises prompt with dynamic word limits"""
    if word_limits is None:
        word_limits = {
            'exercises': 800
        }
    return f"""You are an expert in science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a science book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate COMPREHENSIVE SCIENCE EXERCISES based on the chapter content in the PDF.
**Target Total Word Count for All Exercises**: {word_limits.get('exercises', 800)} words

**Core Science Exercise Types:**

Create the following science exercise types:
1. **MCQ (Multiple Choice Questions)** - at least 10 questions with scientific reasoning
2. **Assertion and Reason (Scientific)** - at least 5 questions testing scientific logic
3. **Fill in the Blanks (Scientific)** - at least 10 questions focusing on scientific terms
4. **True False (Scientific)** - at least 10 statements with scientific justification
5. **Define the following scientific terms** - at least 10 terms from the chapter
6. **Match the column (Scientific)** - at least 2 sets with 5 scientific matches each
7. **Give Reason for the following Scientific Statement (Easy Level)** - at least 5 questions
8. **Answer in Brief (Moderate Level)** - at least 5 questions on scientific concepts
9. **Answer in Detail (Hard Level)** - at least 5 questions requiring scientific explanation

**Special Science Features:**
- **Scientific Investigation Questions**: Include questions that require scientific thinking
- **Experimental Design**: Questions about planning and conducting scientific experiments
- **Data Analysis**: Questions involving interpretation of scientific data and graphs
- **Real-world Applications**: Connect scientific concepts to everyday phenomena
- **Cross-curricular Connections**: Link science to mathematics, technology, and environment

Ensure that:
* Questions cover ALL important scientific concepts from the PDF
* Questions follow Bloom's Taxonomy at various levels (Remember, Understand, Apply, Analyze, Evaluate, Create)
* Scientific language is clear and appropriate for {grade_level}
* Questions increase in difficulty from basic scientific recall to higher-order scientific thinking
* All exercises include correct answers or model scientific solutions
* Content is formatted in Markdown with proper scientific notation
* Questions encourage scientific inquiry and critical thinking
* Include questions that test understanding of scientific processes and methods

Do NOT directly copy questions from the PDF. Create new, original scientific questions based on the content.

Provide ONLY the comprehensive science exercises in Markdown format.
"""

def create_science_skills_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a science subject skills and STEM activities prompt with dynamic word limits"""
    if word_limits is None:
        word_limits = {
            'skill_activity': 400,
            'stem_activity': 400
        }
    return f"""You are an expert in science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a science book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate SCIENCE SKILL-BASED ACTIVITIES and STEM projects based on the chapter content in the PDF.

## Science Skill-Based Activities (Target: {word_limits.get('skill_activity', 400)} words)

Create at least 3 hands-on science activities that:
* Reinforce the key scientific concepts from the chapter
* Develop practical scientific skills relevant to the subject
* Can be completed with easily available scientific materials
* Include clear step-by-step scientific procedures
* Encourage scientific observation and data collection
* Connect to scientific method and inquiry-based learning

**Activity Structure for Each:**
1. **Clear Scientific Objective**
2. **Scientific Materials Required**
3. **Step-by-Step Scientific Procedure**
4. **Scientific Observations to Record**
5. **Data Collection and Analysis**
6. **Safety Precautions for Science Activities**
7. **Scientific Reflection Questions**
8. **Expected Scientific Outcomes and Learning**

## Science STEM Projects (Target: {word_limits.get('stem_activity', 400)} words)

Create at least 2 comprehensive STEM projects that:
* Integrate Science, Technology, Engineering and Mathematics
* Connect to real-world scientific applications of the chapter concepts
* Encourage scientific problem-solving and critical thinking
* Include scientific materials needed, procedure, and expected outcomes
* Promote scientific investigation and evidence-based conclusions
* Link to current scientific research and technological developments

**STEM Project Structure for Each:**
1. **Scientific Integration Focus**
2. **Real-World Scientific Application**
3. **Technology Integration in Science**
4. **Engineering Design Challenge**
5. **Mathematical Analysis of Scientific Data**
6. **Scientific Methodology and Process**
7. **Scientific Communication and Presentation**
8. **Assessment Criteria for Scientific Understanding**

**Special Science Features:**
- **Scientific Investigation**: Include projects that require hypothesis formation and testing
- **Environmental Connections**: Link activities to environmental science and sustainability
- **Technology Integration**: Use digital tools for data collection and analysis
- **Career Connections**: Connect to science, technology, engineering careers
- **Safety First**: Emphasize scientific safety protocols in all activities

For each activity/project, include:
* A clear scientific title and learning objective
* Complete list of scientific materials required
* Detailed scientific procedure with numbered steps
* Safety precautions for scientific activities
* Scientific observation charts and data collection sheets
* Reflection questions that promote scientific thinking
* Expected scientific outcomes and learning points
* Connections to scientific careers and real-world applications

Format the content in Markdown with proper scientific headings, lists, and organization.

Provide ONLY the Science Skill Activities and STEM Projects in Markdown format.
"""

def create_science_art_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a science subject art integration prompt with dynamic word limits"""
    if word_limits is None:
        word_limits = {
            'art_learning': 400
        }
    return f"""You are an expert in science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a science book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate SCIENCE-INTEGRATED CREATIVE LEARNING projects based on the chapter content in the PDF.
**Target Total Word Count for All Art-Integrated Learning**: {word_limits.get('art_learning', 400)} words

## Science Art Projects

Create at least 3 creative projects that connect scientific concepts to various art forms:

**Project Structure for Each:**
1. **Scientific Learning Objective**
2. **Art Form Integration with Science**
3. **Scientific Concepts Highlighted**
4. **Materials and Scientific Tools**
5. **Step-by-Step Scientific-Artistic Process**
6. **Scientific Observation and Documentation**
7. **Scientific Reflection and Analysis**
8. **Showcase and Scientific Communication**

**Types of Science Art Integration:**
- **Scientific Visualization**: Create artistic representations of scientific processes
- **Science Through Music**: Use rhythm and sound to represent scientific patterns
- **Scientific Drama**: Act out scientific processes and phenomena
- **Digital Science Art**: Use technology to create scientific visualizations
- **Scientific Models and Sculptures**: 3D representations of scientific concepts

## Scientific Case Studies

**Case Study – Level 1 (Accessible Scientific Analysis):**
Create at least 1 simpler case study that:
- Presents a real-world scientific scenario appropriate for {grade_level}
- Includes guided scientific analysis questions
- Is accessible to all students with basic scientific knowledge
- Connects to current scientific events or discoveries

**Case Study – Level 2 (Advanced Scientific Challenge):**
Create at least 1 more complex case study that:
- Challenges students with multi-step scientific problems
- Requires deeper application of scientific concepts
- Encourages higher-order scientific thinking skills
- Includes data analysis and scientific reasoning

**Scientific Case Study Structure for Each:**
1. **Real-World Scientific Context**
2. **Scientific Background Information**
3. **Guided Scientific Questions**
4. **Scientific Data and Evidence**
5. **Analysis Requirements**
6. **Creative Scientific Solutions**
7. **Scientific Communication Component**
8. **Extension Scientific Challenges**

**Special Science Integration Features:**
- **Environmental Connections**: Link art projects to environmental science
- **Scientific Method Integration**: Include hypothesis, observation, and conclusion
- **Technology Tools**: Use digital tools for scientific art creation
- **Scientific Communication**: Present findings through artistic expression
- **Cross-Curricular Connections**: Connect science to mathematics, geography, and history

For each project/case study, include:
* A clear scientific title and learning objective
* Complete list of materials needed (scientific and artistic supplies)
* Detailed scientific-artistic instructions or scenario description
* Scientific observation sheets and reflection questions
* Assessment criteria for both scientific understanding and creative expression
* Connections to scientific careers and real-world applications
* Safety considerations for scientific art activities

Format the content in Markdown with proper scientific and artistic headings, lists, and organization.

Provide ONLY the Science-Integrated Creative Learning content in Markdown format.
"""

# Computer Science specific prompt functions
def create_computer_chapter_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a computer science-specific chapter content prompt"""
    # Default word limits if none provided
    if word_limits is None:
        word_limits = {
            'hook': 80,
            'learning_outcome': 70,
            'real_world': 70,
            'previous_class': 100,
            'current_concepts': 4500,
            'summary': 100,
            'exercises': 1000,
            'skill_activity': 100
        }
    
    return f"""You are an expert in computer science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes.

You are analyzing a computer science book chapter intended for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines for Computer Science education.

**CRITICAL INSTRUCTION**: The PDF may contain MULTIPLE MAJOR SECTIONS (e.g., Section 1, Section 2, Section 3, etc.). You MUST include ALL sections present in the PDF. Do NOT stop after completing just one or two sections. Generate comprehensive content for EVERY section found in the document.

**Model Chapter Progression and Elements (Base Structure):**
---
{model_progression_text}
---

**Target Audience:** {grade_level} (CBSE Computer Science Syllabus)

Your task is to generate COMPREHENSIVE COMPUTER SCIENCE CHAPTER CONTENT following the Model Chapter Progression structure enhanced with computer science-specific elements.

**IMPORTANT**: If the PDF contains multiple sections, you MUST generate complete content for EACH section. The structure below should be applied to EACH major section in the PDF.

**REQUIRED SECTIONS (Generate ALL with substantial content for EACH major section in the PDF):**

## I. Chapter Opener

1. **Chapter Title** - Engaging and technology-focused

2. **Hook (with Image Prompt)** (Target: {word_limits.get('hook', 80)} words)
   - Create an engaging technological opening that captures student interest
   - Use real-life technology scenarios, digital innovations, or computational challenges
   - Connect to students' digital experiences and interests
   - Include a detailed image prompt for a compelling tech visual

3. **Real-World Connection** (Target: {word_limits.get('real_world', 70)} words)
   - Provide multiple real-world applications of the computer science concepts
   - Show how technology is transforming various industries
   - Include examples from gaming, apps, AI, robotics, web development, etc.
   - Connect to tech careers and future opportunities

4. **Learning Outcomes** (Target: {word_limits.get('learning_outcome', 70)} words)
   - List specific, measurable computer science learning objectives
   - Use action verbs (code, debug, design, implement, analyze, create, etc.)
   - Align with Bloom's Taxonomy for computational thinking
   - Connect to CBSE computer science curriculum standards

5. **Previous Class Link** (Target: {word_limits.get('previous_class', 100)} words)
   - Link to prior computer science knowledge from previous classes
   - Explain how previous concepts build into current learning
   - Provide a brief review of essential prerequisites

6. **Chapter Map/Overview** (100 words)
   - Visual layout of computer science concepts (flowchart or mind map description)
   - Show progression from basic to advanced concepts

7. **Meet the Character (EeeBee)** (30-50 words)
   - Introduce EeeBee as a digital guide/coding buddy throughout the chapter

## II. Core Content Sections (REPEAT FOR EACH MAJOR SECTION IN THE PDF)

8. **Introduction of Section** (150 words per section)
   - Give a related section introduction that sets the technological context
   - Explain the importance of the computer science concepts to be learned
   - Connect to the broader digital literacy curriculum

9. **Warm-up Activities** (100 words per section)
   - Create 5-7 engaging warm-up activities that connect to prior tech knowledge
   - Include unplugged activities, quick challenges, or digital puzzles

10. **Current Concepts** (Target: {word_limits.get('current_concepts', 4500)} words minimum PER SECTION)
    
    For each major concept in EACH section, include ALL of the following:
    
    **A. Concept Introduction** (100 words per concept)
    - Clear introduction to each computer science concept
    - Simple, accessible language with technical terms explained
    - Use analogies from everyday life
    
    **B. Technical Explanation** (400-500 words per concept)
    - Detailed theoretical understanding of the concept
    - Include technical specifications, algorithms, or processes
    - Show different approaches and methodologies
    
    **C. Hands-on Examples** (500-600 words per concept)
    - Provide 4-5 different practical examples
    - Include step-by-step implementations
    - Show code snippets (if applicable) with clear explanations
    - Use varied difficulty levels
    
    **D. Practice Exercises** (400-500 words per concept)
    Create the following specific computer science question types for each concept:
    
    1. **Code Completion** - 3-4 exercises
       - Fill in missing parts of code or algorithms
    
    2. **Debug the Code** - 2 exercises
       - Find and fix errors in given code snippets
    
    3. **Algorithm Design** - 3 exercises
       - Design solutions for given problems
    
    4. **Output Prediction** - 3 exercises
       - Predict the output of given code
    
    5. **Tech Application Questions** - 5 questions
       - Real-world scenarios using the concept
    
    6. **Computational Thinking Puzzles** - 3 questions
       - Logic puzzles and problem-solving challenges
    
    **E. Lab Activities** (300-400 words per concept)
    - Step-by-step computer lab exercises
    - Include both online and offline activities
    - Specify software/tools required
    
    **F. Visual Representations** (Throughout each concept)
    - Include detailed image prompts for flowcharts, diagrams, screenshots
    - User interface mockups where applicable
    
    **G. Try It Yourself** (200-250 words per concept)
    - Mini-projects or coding challenges
    - Encourage experimentation and creativity
    
    **H. Key Technical Terms** (100-150 words per concept)
    - Highlighted technical vocabulary
    - Clear definitions with examples
    
    **I. Tech Facts** (100-150 words per concept)
    - Interesting facts about the technology
    - Current trends and future possibilities
    
    **J. Quick Tips** (150-200 words per concept)
    - Best practices and shortcuts
    - Common mistakes to avoid
    
    **K. Fun With Colors** (50-80 words per concept)
    - Color-coded programming concepts or visual elements
    - Creative activities using colors to understand technical concepts
    
    **L. Unscramble the Letters** (30-50 words per concept)
    - Word puzzles related to computer science terminology
    - Technical vocabulary building exercises
    
    **M. Health, Safety & Ethics Corner/Computer Etiquettes** (100-120 words per concept)
    - Digital wellness and ergonomics
    - Ethical considerations in technology use
    - Proper computer usage and digital citizenship
    
    **N. Shortcut Keys** (50-80 words per concept)
    - Relevant keyboard shortcuts for the concept
    - Efficiency tips for computer operations

## IV. Chapter Wrap-Up (For the ENTIRE chapter)

11. **Common Programming Errors** (80-100 words)
    - 2-3 common mistakes per concept
    - How to identify and fix them

12. **Summary/Points to Remember** (Target: {word_limits.get('summary', 100)} words)
    - Key takeaways from the chapter
    - Essential concepts and skills learned
    - Important technical points to remember

13. **Self-Assessment Checklist** (80-100 words)
    - Programming skills checklist
    - Concept understanding verification

14. **Chapter-wise Lab Exercise** (Target: {word_limits.get('exercises', 1000)} words)
    - Comprehensive Lab Project
    - Multiple Choice Questions (5)
    - Fill in the Blanks (5)
    - Abbreviations (5)
    - Debugging Exercises (3)
    - Match The Following (5)
    - Code Writing Tasks (3)
    - Technical Concept Mapping
    - True/False with Explanation (5)
    - Case Study Analysis (1)
    - Innovation Challenge (1)
    - Answer the Following Questions - Short (5)
    - Answer the Following Questions - Long (5)

15. **Apply Your Digital Skills** (Target: {word_limits.get('skill_activity', 100)} words)
    - Real-world technology project
    - Cross-curricular integration

**CONTENT REQUIREMENTS:**
* **CRITICAL**: Include ALL major sections from the PDF
* **Technical Accuracy**: Ensure all code and technical content is accurate
* **Age-Appropriate Complexity**: Match technical depth to grade level
* **Practical Focus**: Balance theory with hands-on practice
* **Progressive Learning**: Structure from basic to advanced
* Include actual code examples appropriate for the grade level
* DO NOT copy code directly from the PDF - create new examples

Provide ONLY the comprehensive computer science chapter content in Markdown format. Remember to include EVERY section found in the PDF document.
"""

def create_computer_exercises_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a computer science-specific exercises prompt"""
    if word_limits is None:
        word_limits = {
            'exercises': 800
        }
    return f"""You are an expert in computer science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a computer science book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate COMPREHENSIVE COMPUTER SCIENCE EXERCISES based on the chapter content in the PDF.
**Target Total Word Count for All Exercises**: {word_limits.get('exercises', 800)} words

**Core Computer Science Exercise Types:**
1. **MCQ (Multiple Choice Questions)** - at least 12 questions covering theory and concepts
2. **Code Completion Exercises** - at least 8 exercises
3. **Debug the Code** - at least 5 exercises with errors to fix
4. **Write the Code** - at least 5 programming tasks
5. **Algorithm Design** - at least 5 problems requiring algorithmic solutions
6. **Output Prediction** - at least 8 code snippets to analyze
7. **True/False with Technical Justification** - at least 10 statements
8. **Fill in the Blanks (Technical)** - at least 10 questions
9. **Match the Following (Tech Terms)** - at least 2 sets with 5 matches each
10. **Flowchart/Diagram Exercises** - at least 3 exercises
11. **Case Studies (Tech Scenarios)** - at least 2 real-world scenarios
12. **Project-Based Questions** - at least 3 mini-project ideas

**Special Computer Science Features:**
- **Lab Exercises**: Step-by-step practical implementations
- **EeeBee Integration**: Include exercises where EeeBee guides problem-solving
- **Digital Tools**: Questions involving specific software/platforms
- **Cyber Ethics**: Include digital citizenship and ethics questions
- **Differentiation**: Basic to advanced level questions

**Programming Languages** (adjust based on grade):
- For lower grades: Block-based coding, Scratch concepts
- For middle grades: Basic Python, HTML/CSS
- For higher grades: Python, Java, SQL, Web technologies

Ensure that:
* Questions cover ALL important computer science concepts from the PDF
* Include practical coding exercises, not just theory
* Questions progress from basic recall to complex problem-solving
* Language and complexity are appropriate for {grade_level}
* All exercises include detailed solutions with explanations
* Code examples use proper syntax and best practices

Provide ONLY the comprehensive computer science exercises in Markdown format.
"""

def create_computer_skills_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a computer science-specific skills and lab activities prompt"""
    if word_limits is None:
        word_limits = {
            'skill_activity': 400,
            'stem_activity': 400
        }
    return f"""You are an expert in computer science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a computer science book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate COMPUTER SCIENCE SKILL-BASED ACTIVITIES and LAB PROJECTS.

## Computer Science Skill-Based Activities (Target: {word_limits.get('skill_activity', 400)} words)

Create at least 3 comprehensive hands-on activities:

**Activity Structure for Each:**
1. **Clear Technical Objective**
2. **Software/Hardware Requirements**
3. **Step-by-Step Implementation**
4. **Code Templates (if applicable)**
5. **Testing and Debugging Steps**
6. **Real-World Applications**
7. **EeeBee's Coding Tips**
8. **Reflection and Documentation**
9. **Expected Output/Results**

**Types of Computer Science Activities:**
- Programming Challenges
- App/Game Development Mini-Projects
- Web Development Tasks
- Database Design Exercises
- Algorithm Implementation
- Digital Art/Animation Creation
- Robotics/IoT Projects (conceptual if hardware unavailable)

## Computer Lab Projects (STEM Integration) (Target: {word_limits.get('stem_activity', 400)} words)

Create at least 2 comprehensive lab projects that integrate computer science with other STEM fields:

**Project Structure for Each:**
1. **Project Title and Overview**
2. **Technical Requirements**
3. **Learning Objectives**
4. **Detailed Implementation Steps**
5. **Code Structure and Templates**
6. **Testing Procedures**
7. **Troubleshooting Guide**
8. **Extensions and Modifications**
9. **Presentation Guidelines**
10. **Assessment Rubric**

**STEM Integration Examples:**
- Data Science Projects (CS + Math)
- Simulation Projects (CS + Science)
- Engineering Design with Code
- Digital Solutions for Real Problems
- AI/ML Demonstrations (age-appropriate)

**Digital Citizenship Component:**
Include for each activity:
- Ethical considerations
- Copyright and licensing awareness
- Online safety practices
- Responsible technology use

Format the content in Markdown with proper code formatting using triple backticks for code blocks.

Provide ONLY the Computer Science Skill Activities and Lab Projects in Markdown format.
"""

def create_computer_art_prompt(grade_level, model_progression_text, word_limits=None):
    """Creates a computer science-specific creative and case study prompt"""
    if word_limits is None:
        word_limits = {
            'art_learning': 400
        }
    return f"""You are an expert in computer science education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

You are analyzing a computer science book chapter intended for **{grade_level} (CBSE)**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

Your task is to generate COMPUTER SCIENCE CREATIVE PROJECTS and CASE STUDIES.
**Target Total Word Count for All Art-Integrated Learning**: {word_limits.get('art_learning', 400)} words

## Digital Creativity Projects

Create at least 3 creative projects that blend computer science with artistic expression:

**Project Structure for Each:**
1. **Creative Tech Objective**
2. **Tools and Technologies Required**
3. **Technical Concepts Applied**
4. **Step-by-Step Creative Process**
5. **Code Components (if applicable)**
6. **EeeBee's Creative Coding Tips**
7. **Showcase and Portfolio Building**
8. **Peer Review Guidelines**

**Types of Digital Creative Projects:**
- Digital Art and Graphics Programming
- Interactive Storytelling with Code
- Game Design and Development
- Animation and Multimedia Projects
- Music and Sound with Code
- AR/VR Concepts (age-appropriate)
- Creative Web Design
- Data Visualization Art

## Technology Case Studies

**Case Study – Level 1 (Foundational Analysis):**
Create at least 1 accessible case study that:
- Presents a real-world technology scenario appropriate for {grade_level}
- Includes guided analysis of technical solutions
- Focuses on problem-solving with technology
- Is accessible to students with basic computer skills

**Case Study – Level 2 (Advanced Challenge):**
Create at least 1 complex case study that:
- Presents multi-faceted technical challenges
- Requires system design thinking
- Involves multiple technologies/concepts
- Encourages innovative solutions

**Case Study Structure for Each:**
1. **Real-World Tech Scenario**
2. **Problem Statement**
3. **Technical Background**
4. **Current Technology Analysis**
5. **Proposed Digital Solutions**
6. **Implementation Considerations**
7. **Code Snippets/Pseudocode**
8. **Ethical and Social Impact**
9. **EeeBee's Tech Insights**
10. **Future Enhancements**

**Innovation Challenges:**
Include for each case study:
- "What if?" scenarios
- Brainstorming prompts
- Prototype development ideas
- Presentation formats

**Digital Portfolio Component:**
- How to document projects
- Building a digital portfolio
- Showcasing work online safely

Format the content in Markdown with proper formatting for code examples.

Provide ONLY the Computer Science Creative Projects and Case Studies in Markdown format.
"""

def generate_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text, subject_type="Science", word_limits=None, use_chunked=False, use_openrouter_method=True):
    """Generates specific content based on content type"""
    if not use_chunked:
        # Standard approach
        try:
            # Get the specific prompt (Mathematics Primary doesn't use model_progression_text)
            if subject_type == "Mathematics Primary (Classes 1-5)":
                prompt = create_specific_prompt(content_type, grade_level, None, subject_type, word_limits)
            else:
                prompt = create_specific_prompt(content_type, grade_level, model_progression_text, subject_type, word_limits)
            
            st.info(f"Generating {content_type} content for {grade_level}...")
            
            if use_openrouter_method:
                # Use OpenRouter's recommended direct PDF upload
                messages = create_messages_with_pdf_openrouter(prompt, pdf_bytes, pdf_filename)
                
                # Configure PDF processing engine
                plugins = [
                    {
                        "id": "file-parser",
                        "pdf": {
                            "engine": "pdf-text"  # or "mistral-ocr" for OCR
                        }
                    }
                ]
                
                # Determine max tokens based on content type
                max_tokens = 131072 if (subject_type == "Mathematics" and content_type == "chapter") else 65536
                
                # Make API call with plugins
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": YOUR_SITE_URL,
                        "X-Title": YOUR_SITE_NAME,
                    },
                    model=MODEL_NAME,
                    messages=messages,
                    plugins=plugins,
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
            else:
                # Use text extraction method (original or Mistral OCR)
                if pdf_method == "Mistral OCR (Advanced)":
                    st.info("🔍 **DEBUG:** Attempting Mistral OCR processing...")
                    # Use Mistral OCR for advanced text extraction
                    pdf_text, pdf_images = process_pdf_with_mistral_ocr(pdf_bytes, pdf_filename)
                    if pdf_text is None:
                        st.error("🔍 **DEBUG:** Mistral OCR failed - returning error")
                        return None, "Failed to process PDF with Mistral OCR"
                    st.success("🔍 **DEBUG:** Mistral OCR succeeded - proceeding with OCR content")
                    # Create messages with Mistral OCR content
                    messages = create_messages_with_mistral_ocr_content(prompt, pdf_text, pdf_images)
                else:
                    st.info(f"🔍 **DEBUG:** Using method: {pdf_method}")
                    # Use original text extraction method
                    pdf_text = extract_text_from_pdf(pdf_bytes)
                    pdf_images = extract_images_from_pdf(pdf_bytes)
                    # Create messages with PDF content
                    messages = create_messages_with_pdf_content(prompt, pdf_text, pdf_images)
                
                # Determine max tokens based on content type
                max_tokens = 131072 if (subject_type == "Mathematics" and content_type == "chapter") else 65536
                
                # Make API call
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": YOUR_SITE_URL,
                        "X-Title": YOUR_SITE_NAME,
                    },
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
            
            result_text = completion.choices[0].message.content
            
            return result_text, "Generated successfully using standard approach."
            
        except Exception as e:
            st.error(f"Error during content generation: {e}")
            if "token" in str(e).lower() or "limit" in str(e).lower():
                st.info("Document might be too large. Trying chunked approach...")
                return generate_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, 
                                               model_progression_text, subject_type, word_limits, use_chunked=True, use_openrouter_method=use_openrouter_method)
            return None, f"Error: {str(e)}"
    else:
        # Chunked approach
        return analyze_with_chunked_approach_for_specific_content(content_type, pdf_bytes, pdf_filename, 
                                                                 grade_level, model_progression_text, subject_type, word_limits, use_openrouter_method, pdf_method)

def analyze_with_chunked_approach_for_specific_content(content_type, pdf_bytes, pdf_filename, 
                                                       grade_level, model_progression_text, subject_type, word_limits, use_openrouter_method=True):
    """Specialized chunked approach for specific content types"""
    st.info(f"Using chunked approach to generate {content_type} content...")
    
    try:
        # Extract text from PDF for determining page chunks
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        # Determine chunk size
        pages_per_chunk = 5
        
        # Process chunks
        analysis_results = []
        
        for start_page in range(0, total_pages, pages_per_chunk):
            end_page = min(start_page + pages_per_chunk - 1, total_pages - 1)
            st.info(f"Analyzing chunk: Pages {start_page+1}-{end_page+1} of {total_pages}...")
            
            # Extract text and images for this chunk
            chunk_text = ""
            chunk_images = []
            
            for page_num in range(start_page, end_page + 1):
                page = doc.load_page(page_num)
                chunk_text += f"\n\n--- Page {page_num + 1} ---\n"
                chunk_text += page.get_text()
                
                # Extract all images
                image_list = page.get_images(full=True)
                for img in image_list:  # Include all images from page
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        base64_image = base64.b64encode(image_bytes).decode('utf-8')
                        ext = base_image["ext"]
                        chunk_images.append({
                            "page": page_num + 1,
                            "base64": f"data:image/{ext};base64,{base64_image}",
                        })
                    except:
                        pass
            
            # Analyze this chunk
            chunk_prompt = f"""You are an expert in educational content development for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: You are analyzing CHUNK (Pages {start_page+1}-{end_page+1} of {total_pages}) from a book chapter for **{grade_level} (CBSE)**.
This is just a PORTION of the full chapter - focus only on this section.

You are extracting information relevant for: {content_type.upper()} CONTENT

Please analyze these specific pages and extract:
* Key concepts, topics, and terminology relevant to {content_type}
* Important facts, examples, and explanations
* For any images, their content and relevance
* Any specific information that would be useful for creating {content_type} content

Format your analysis in Markdown. This is just an intermediate step - don't create final content yet.
"""
            
            try:
                if use_openrouter_method:
                    # For chunked OpenRouter approach, we'll need to create a temporary PDF for this chunk
                    # This is a limitation - OpenRouter expects a full PDF, not partial text
                    # So we'll fall back to text-based approach for chunks
                    messages = create_messages_with_pdf_content(chunk_prompt, chunk_text, chunk_images)
                else:
                    messages = create_messages_with_pdf_content(chunk_prompt, chunk_text, chunk_images)
                
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": YOUR_SITE_URL,
                        "X-Title": YOUR_SITE_NAME,
                    },
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=32768,
                    temperature=0.3,
                )
                
                analysis_chunk = completion.choices[0].message.content
                analysis_results.append(analysis_chunk)
                
            except Exception as chunk_e:
                st.warning(f"Error processing chunk: {chunk_e}")
                analysis_results.append(f"[Error processing pages {start_page+1}-{end_page+1}]")
        
        doc.close()
        
        # Combine chunk analyses
        combined_analyses = "\n\n".join(analysis_results)
        
        # Get the specific prompt for this content type
        specific_prompt = create_specific_prompt(content_type, grade_level, model_progression_text, subject_type, word_limits)
        
        # Create the final integration prompt
        integration_prompt = f"""You are an expert educational content developer for CBSE curriculum.
You have been given analyses of different chunks of a book chapter for **{grade_level} (CBSE)**.
Your task is to create comprehensive {content_type.upper()} content based on these analyses.

This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

**Content Type Requirements:**
{specific_prompt}

**Analyses from different parts of the chapter:**
{combined_analyses}

Based on these analyses, create the complete {content_type.upper()} content in Markdown format.
Ensure it is cohesive, well-structured, and follows all the requirements for {content_type} content.
"""
        
        # Generate the final content
        st.info(f"Creating final {content_type} content...")
        
        try:
            # Determine max tokens
            max_tokens = 131072 if (subject_type == "Mathematics" and content_type == "chapter") else 65536
            
            messages = [{"role": "user", "content": integration_prompt}]
            
            final_completion = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": YOUR_SITE_URL,
                    "X-Title": YOUR_SITE_NAME,
                },
                model=MODEL_NAME,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
            )
            
            final_content = final_completion.choices[0].message.content
            
            return final_content, "Generated successfully using chunked approach."
            
        except Exception as integration_e:
            st.error(f"Error during final integration: {integration_e}")
            return combined_analyses, "Partial analysis complete - final integration failed."
            
    except Exception as e:
        st.error(f"Error during chunked analysis: {e}")
        return None, f"Error during chunked analysis: {str(e)}"

def encode_pdf_to_base64(pdf_bytes):
    """Encodes PDF bytes to base64 string for OpenRouter API."""
    return base64.b64encode(pdf_bytes).decode('utf-8')

def create_messages_with_pdf_openrouter(prompt, pdf_bytes, pdf_filename):
    """Creates messages array for OpenRouter API with direct PDF upload."""
    # Encode PDF to base64
    base64_pdf = encode_pdf_to_base64(pdf_bytes)
    data_url = f"data:application/pdf;base64,{base64_pdf}"
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "file",
                    "file": {
                        "filename": pdf_filename,
                        "file_data": data_url
                    }
                }
            ]
        }
    ]
    
    return messages

def analyze_with_llm_openrouter(pdf_file_bytes, pdf_filename, model_progression_text, grade_level):
    """Analyzes the uploaded PDF chapter using OpenRouter's direct PDF upload approach."""
    st.info("Processing PDF for analysis...")
    
    prompt_content = f"""You are an expert in educational content development, specifically for CBSE curriculum.
Your task is to analyze the provided PDF document, which is a book chapter intended for **{grade_level} (CBSE)**.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes. Please proceed with the analysis and rewriting.

You need to evaluate it against the 'Model Chapter Progression and Elements' provided below.
The final output should be a completely rewritten and improved chapter that incorporates all necessary corrections and adheres to the model, suitable for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines. The book should be according to the NCERT books for **{grade_level}**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

**REQUIRED CONTENT STRUCTURE:**
The improved chapter MUST follow this specific structure:
1. Current Concepts
2. Hook (with Image Prompt)
3. Learning Outcome
4. Real world connection
5. Previous class concept
6. History
7. Summary
10. Exercise (with the following 5 question types, each with appropriate number of questions):
   - MCQ
   - Assertion and Reason
   - Fill in the Blanks
   - True False
   - Define the following terms
   - Match the column
   - Give Reason for the following Statement (Easy Level)
   - Answer in Brief (Moderate Level)
   - Answer in Detail (Hard Level)
11. Skill based Activity
12. Activity Time – STEM
13. Creativity – Art
14. Case Study – Level 1
15. Case Study – Level 2

**Target Audience:** {grade_level} (CBSE Syllabus)

**Important Formatting Requirements:**
* Format like a proper textbook with well-structured paragraphs (not too long but sufficiently developed)
* Use clear headings and subheadings to organize content
* Include multiple Bloom's Taxonomy questions at different levels in each relevant section
* Create concept-wise summaries (visuals are optional but helpful)
* Integrate special features within the core concept flow rather than as separate sections
* DO NOT change the original concept names/terminology from the uploaded PDF

**Instructions for Analysis and Rewrite:**
1.  **Read and understand the entire PDF chapter.** Pay attention to text, images, diagrams, and overall structure, keeping the **{grade_level}** student in mind.
2.  **Compare the chapter to each element** in the 'Model Chapter Progression and Elements'.
3.  **Identify deficiencies:** Where does the uploaded chapter fall short for a **{grade_level}** audience and the model? Be specific.
4.  **Analyze Images:** For each image in the PDF, assess its:
    *   Relevance to the surrounding text and learning objectives for **{grade_level}**.
    *   Clarity and quality.
    *   Age-appropriateness for **{grade_level}**.
    *   Presence of any specific characters if expected (e.g., 'EeeBee').
5.  **Suggest Image Actions:**
    *   If an image is good, state that it should be kept.
    *   If an image needs improvement (e.g., better clarity, different focus for **{grade_level}**), describe the improvement.
    *   If an image is irrelevant, unsuitable, or missing, provide a detailed prompt for an AI image generator to create a new, appropriate image suitable for **{grade_level}**. The prompt should be clearly marked, e.g., "[PROMPT FOR NEW IMAGE: A detailed description of the image needed, including style, content, characters like 'EeeBee' if applicable, and educational purpose for **{grade_level}**.]"
6.  **Rewrite the Chapter:** Create a new version of the chapter that:
    *   Follows the 'Model Chapter Progression and Elements' strictly.
    *   MUST include ALL elements from the REQUIRED CONTENT STRUCTURE in the order specified.
    *   Corrects all identified mistakes and deficiencies.
    *   Integrates image feedback directly into the text.
    *   Ensures content is aligned with NCERT, NCF, and NEP 2020 principles (e.g., inquiry-based learning, 21st-century skills, real-world connections) appropriate for **{grade_level}**.
    *   Is written in clear, engaging, and age-appropriate language for **{grade_level} (CBSE)**.
    *   Use Markdown for formatting (headings, bold, italics, lists) to make it easy to convert to a Word document. For example:
        # Chapter Title
        ## Section Title
        **Bold Text**
        *Italic Text*
        - Item 1
        - Item 2
    *   Present content in proper textbook paragraphs like a NCERT textbook
    *   Include multiple Bloom's Taxonomy questions at various levels (Remember, Understand, Apply, Analyze, Evaluate, Create) in each appropriate section
    *   Organize summaries by individual concepts rather than as a single summary
    *   Weave special features (misconceptions, 21st century skills, etc.) into the core concept flow
    *   PRESERVE all original concept names and terminology from the source PDF

IMPORTANT: Do NOT directly copy large portions of text from the PDF. Instead, use your own words to rewrite and improve the content while maintaining the original concepts and terminology.

**Output Format:**
Provide the complete, rewritten chapter text in Markdown format, incorporating all analyses and image prompts as described. Do not include a preamble or a summary of your analysis; just the final chapter content.
"""
    
    st.info(f"Sending request to Claude via OpenRouter for {grade_level}... This may take some time for larger documents.")
    
    try:
        # Create messages with direct PDF upload
        messages = create_messages_with_pdf_openrouter(prompt_content, pdf_file_bytes, pdf_filename)
        
        # Optional: Configure PDF processing engine
        plugins = [
            {
                "id": "file-parser",
                "pdf": {
                    "engine": "pdf-text"  # or "mistral-ocr" for OCR
                }
            }
        ]
        
        # Make API call with plugins
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": YOUR_SITE_URL,
                "X-Title": YOUR_SITE_NAME,
            },
            model=MODEL_NAME,
            messages=messages,
            plugins=plugins,  # Add plugins for PDF processing
            max_tokens=65536,
            temperature=0.3,
        )
        
        improved_text = completion.choices[0].message.content
        
        return improved_text, "LLM analysis and rewrite complete using Claude via OpenRouter with direct PDF upload."
        
    except Exception as e:
        st.error(f"Error during OpenRouter API call: {e}")
        # Fallback to the original text extraction method
        st.info("Trying alternative method with text extraction...")
        return analyze_with_llm(pdf_file_bytes, pdf_filename, model_progression_text, grade_level)

def generate_chat_response(user_prompt, chat_history, uploaded_files, grade_level, subject):
    """Generate a response from EeeBee for the chat interface"""
    try:
        # Build context from chat history
        conversation_context = ""
        if len(chat_history) > 1:
            recent_messages = chat_history[-6:]  # Keep last 6 messages for context
            for msg in recent_messages[:-1]:  # Exclude the current message
                conversation_context += f"{msg['role'].title()}: {msg['content']}\n"
        
        # Build system prompt for EeeBee
        system_prompt = f"""You are EeeBee, an expert educational content development assistant specializing in CBSE curriculum.
You help content teams create, modify, and improve educational materials that align with NCERT, NCF, and NEP 2020 guidelines.

Context:
- Target Grade: {grade_level}
- Subject Area: {subject}
- This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY

Your expertise includes:
- Content creation and improvement for CBSE curriculum
- Curriculum alignment and standards compliance
- Age-appropriate content development
- Educational activity design
- Assessment and exercise creation
- Pedagogical best practices
- Integration of 21st-century skills

Guidelines:
- Be helpful, friendly, and professional
- Provide detailed, actionable advice
- Reference educational standards and best practices
- Suggest specific improvements or modifications
- Ask clarifying questions when needed
- Maintain consistency with CBSE/NCERT guidelines

Previous conversation:
{conversation_context}

Current user question: {user_prompt}"""

        # Prepare content parts
        content_parts = [{"type": "text", "text": system_prompt}]
        
        # Add uploaded PDFs if any
        if uploaded_files:
            for uploaded_file in uploaded_files:
                try:
                    # Extract text from PDF
                    pdf_bytes = uploaded_file.getvalue()
                    pdf_text = extract_text_from_pdf(pdf_bytes)
                    
                    if pdf_text:
                        content_parts.append({
                            "type": "text",
                            "text": f"\n\nContent from {uploaded_file.name}:\n{pdf_text[:10000]}"  # Limit text length
                        })
                    
                except Exception as e:
                    st.warning(f"Could not process {uploaded_file.name}: {e}")
        
        # Create messages
        messages = [{"role": "user", "content": content_parts}]
        
        # Generate response
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": YOUR_SITE_URL,
                "X-Title": YOUR_SITE_NAME,
            },
            model=MODEL_NAME,
            messages=messages,
            max_tokens=8192,
            temperature=0.7,
        )
        
        return completion.choices[0].message.content
            
    except Exception as e:
        return f"I encountered an error: {str(e)}. Please try asking your question again or check if your uploaded files are valid PDFs."

def generate_chat_response_stream(user_prompt, chat_history, uploaded_files, grade_level, subject):
    """Generate a streaming response from EeeBee for the chat interface using requests"""
    try:
        # Build context from chat history
        conversation_context = ""
        if len(chat_history) > 1:
            recent_messages = chat_history[-6:]  # Keep last 6 messages for context
            for msg in recent_messages[:-1]:  # Exclude the current message
                conversation_context += f"{msg['role'].title()}: {msg['content']}\n"
        
        # Build system prompt for EeeBee
        system_prompt = f"""You are EeeBee, an expert educational content development assistant specializing in CBSE curriculum.
You help content teams create, modify, and improve educational materials that align with NCERT, NCF, and NEP 2020 guidelines.

Context:
- Target Grade: {grade_level}
- Subject Area: {subject}
- This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY

Your expertise includes:
- Content creation and improvement for CBSE curriculum
- Curriculum alignment and standards compliance
- Age-appropriate content development
- Educational activity design
- Assessment and exercise creation
- Pedagogical best practices
- Integration of 21st-century skills

Guidelines:
- Be helpful, friendly, and professional
- Provide detailed, actionable advice
- Reference educational standards and best practices
- Suggest specific improvements or modifications
- Ask clarifying questions when needed
- Maintain consistency with CBSE/NCERT guidelines

Previous conversation:
{conversation_context}

Current user question: {user_prompt}"""

        # Prepare content parts
        content_parts = [{"type": "text", "text": system_prompt}]
        
        # Add uploaded PDFs if any
        if uploaded_files:
            for uploaded_file in uploaded_files:
                try:
                    # For chat, we'll use the Direct PDF Upload method
                    pdf_bytes = uploaded_file.getvalue()
                    pdf_filename = uploaded_file.name
                    
                    # Encode PDF to base64
                    base64_pdf = encode_pdf_to_base64(pdf_bytes)
                    data_url = f"data:application/pdf;base64,{base64_pdf}"
                    
                    # Add as file in content
                    content_parts.append({
                        "type": "file",
                        "file": {
                            "filename": pdf_filename,
                            "file_data": data_url
                        }
                    })
                    
                except Exception as e:
                    st.warning(f"Could not process {uploaded_file.name}: {e}")
        
        # Create messages
        messages = [{"role": "user", "content": content_parts}]
        
        # Use the streaming function
        cancel_event = st.session_state.get('chat_cancel_event', Event())
        
        for chunk in stream_openrouter_response(
            messages=messages,
            model_name=MODEL_NAME,
            max_tokens=8192,
            temperature=0.7,
            plugins=[{"id": "file-parser", "pdf": {"engine": "pdf-text"}}] if uploaded_files else None,
            cancel_event=cancel_event
        ):
            yield chunk
            
    except Exception as e:
        yield f"I encountered an error: {str(e)}. Please try asking your question again or check if your uploaded files are valid PDFs."

# --- Streaming Support Functions ---
def stream_openrouter_response(messages, model_name, max_tokens, temperature, plugins=None, cancel_event=None):
    """
    Stream responses from OpenRouter API with cancellation support.
    Returns a generator that yields response chunks.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,
        "X-Title": YOUR_SITE_NAME,
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True
    }
    
    if plugins:
        payload["plugins"] = plugins
    
    try:
        with requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=300  # 5 minute timeout
        ) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if cancel_event and cancel_event.is_set():
                    response.close()
                    yield "[CANCELLED] Generation cancelled by user."
                    return
                    
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]  # Remove 'data: ' prefix
                        if data_str == '[DONE]':
                            return
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
                            
    except requests.exceptions.RequestException as e:
        yield f"\n\n[ERROR] Request failed: {str(e)}"
    except Exception as e:
        yield f"\n\n[ERROR] Unexpected error: {str(e)}"

def analyze_with_llm_streaming(pdf_file_bytes, pdf_filename, model_progression_text, grade_level, use_openrouter_method=False):
    """
    Analyzes the uploaded PDF chapter with streaming support.
    Returns a generator that yields response chunks.
    """
    # Create the prompt (same as before)
    prompt_content = f"""You are an expert in educational content development, specifically for CBSE curriculum.
Your task is to analyze the provided PDF document, which is a book chapter intended for **{grade_level} (CBSE)**.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes. Please proceed with the analysis and rewriting.

You need to evaluate it against the 'Model Chapter Progression and Elements' provided below.
The final output should be a completely rewritten and improved chapter that incorporates all necessary corrections and adheres to the model, suitable for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines. The book should be according to the NCERT books for **{grade_level}**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

**REQUIRED CONTENT STRUCTURE:**
The improved chapter MUST follow this specific structure:
1. Current Concepts
2. Hook (with Image Prompt)
3. Learning Outcome
4. Real world connection
5. Previous class concept
6. History
7. Summary
10. Exercise (with the following 5 question types, each with appropriate number of questions):
   - MCQ
   - Assertion and Reason
   - Fill in the Blanks
   - True False
   - Define the following terms
   - Match the column
   - Give Reason for the following Statement (Easy Level)
   - Answer in Brief (Moderate Level)
   - Answer in Detail (Hard Level)
11. Skill based Activity
12. Activity Time – STEM
13. Creativity – Art
14. Case Study – Level 1
15. Case Study – Level 2

**Target Audience:** {grade_level} (CBSE Syllabus)

**Important Formatting Requirements:**
* Format like a proper textbook with well-structured paragraphs (not too long but sufficiently developed)
* Use clear headings and subheadings to organize content
* Include multiple Bloom's Taxonomy questions at different levels in each relevant section
* Create concept-wise summaries (visuals are optional but helpful)
* Integrate special features within the core concept flow rather than as separate sections
* DO NOT change the original concept names/terminology from the uploaded PDF

**Instructions for Analysis and Rewrite:**
1.  **Read and understand the entire PDF chapter.** Pay attention to text, images, diagrams, and overall structure, keeping the **{grade_level}** student in mind.
2.  **Compare the chapter to each element** in the 'Model Chapter Progression and Elements'.
3.  **Identify deficiencies:** Where does the uploaded chapter fall short for a **{grade_level}** audience and the model? Be specific.
4.  **Analyze Images:** For each image in the PDF, assess its:
    *   Relevance to the surrounding text and learning objectives for **{grade_level}**.
    *   Clarity and quality.
    *   Age-appropriateness for **{grade_level}**.
    *   Presence of any specific characters if expected (e.g., 'EeeBee').
5.  **Suggest Image Actions:**
    *   If an image is good, state that it should be kept.
    *   If an image needs improvement (e.g., better clarity, different focus for **{grade_level}**), describe the improvement.
    *   If an image is irrelevant, unsuitable, or missing, provide a detailed prompt for an AI image generator to create a new, appropriate image suitable for **{grade_level}**. The prompt should be clearly marked, e.g., "[PROMPT FOR NEW IMAGE: A detailed description of the image needed, including style, content, characters like 'EeeBee' if applicable, and educational purpose for **{grade_level}**.]"
6.  **Rewrite the Chapter:** Create a new version of the chapter that:
    *   Follows the 'Model Chapter Progression and Elements' strictly.
    *   MUST include ALL elements from the REQUIRED CONTENT STRUCTURE in the order specified.
    *   Corrects all identified mistakes and deficiencies.
    *   Integrates image feedback directly into the text.
    *   Ensures content is aligned with NCERT, NCF, and NEP 2020 principles (e.g., inquiry-based learning, 21st-century skills, real-world connections) appropriate for **{grade_level}**.
    *   Is written in clear, engaging, and age-appropriate language for **{grade_level} (CBSE)**.
    *   Use Markdown for formatting (headings, bold, italics, lists) to make it easy to convert to a Word document.
    *   Present content in proper textbook paragraphs like a NCERT textbook
    *   Include multiple Bloom's Taxonomy questions at various levels (Remember, Understand, Apply, Analyze, Evaluate, Create) in each appropriate section
    *   Organize summaries by individual concepts rather than as a single summary
    *   Weave special features (misconceptions, 21st century skills, etc.) into the core concept flow
    *   PRESERVE all original concept names and terminology from the source PDF

IMPORTANT: Do NOT directly copy large portions of text from the PDF. Instead, use your own words to rewrite and improve the content while maintaining the original concepts and terminology.

**Output Format:**
Provide the complete, rewritten chapter text in Markdown format, incorporating all analyses and image prompts as described. Do not include a preamble or a summary of your analysis; just the final chapter content.
"""
    
    if use_openrouter_method:
        # Create messages with direct PDF upload
        messages = create_messages_with_pdf_openrouter(prompt_content, pdf_file_bytes, pdf_filename)
        plugins = [{"id": "file-parser", "pdf": {"engine": "pdf-text"}}]
    else:
        # Extract text and images from PDF
        pdf_text = extract_text_from_pdf(pdf_file_bytes)
        pdf_images = extract_images_from_pdf(pdf_file_bytes)
        messages = create_messages_with_pdf_content(prompt_content, pdf_text, pdf_images)
        plugins = None
    
    # Create cancel event (can be controlled from UI)
    cancel_event = st.session_state.get('cancel_event', Event())
    
    # Stream the response
    for chunk in stream_openrouter_response(
        messages=messages,
        model_name=MODEL_NAME,
        max_tokens=65536,
        temperature=0.3,
        plugins=plugins,
        cancel_event=cancel_event
    ):
        yield chunk

def generate_specific_content_streaming(content_type, pdf_bytes, pdf_filename, grade_level, 
                                       model_progression_text, subject_type, word_limits, use_openrouter_method):
    """
    Generates specific content with streaming support.
    Returns a generator that yields response chunks.
    """
    # Get the specific prompt (Mathematics Primary doesn't use model_progression_text)
    if subject_type == "Mathematics Primary (Classes 1-5)":
        prompt = create_specific_prompt(content_type, grade_level, None, subject_type, word_limits)
    else:
        prompt = create_specific_prompt(content_type, grade_level, model_progression_text, subject_type, word_limits)
    
    # Always use OpenRouter Direct PDF Upload for optimal performance
    messages = create_messages_with_pdf_openrouter(prompt, pdf_bytes, pdf_filename)
    plugins = [{"id": "file-parser", "pdf": {"engine": "pdf-text"}}]
    
    # Determine max tokens based on content type (reduced for streaming reliability)
    max_tokens = 32768 if (subject_type == "Mathematics" and content_type == "chapter") else 16384
    
    # Create cancel event (can be controlled from UI)
    cancel_event = st.session_state.get('cancel_event', Event())
    
    # Stream the response
    for chunk in stream_openrouter_response(
        messages=messages,
        model_name=MODEL_NAME,
        max_tokens=max_tokens,
        temperature=0.3,
        plugins=plugins,
        cancel_event=cancel_event
    ):
        yield chunk

def handle_streaming_generation(content_type, pdf_bytes, pdf_filename, selected_grade, 
                               model_progression, subject_type, word_limits, button_key):
    """Helper function to handle streaming content generation with UI"""
    # Initialize cancel event for streaming
    st.session_state.cancel_event = Event()
    cancel_col1, cancel_col2 = st.columns([5, 1])
    with cancel_col2:
        cancel_button = st.button("🛑 Cancel", key=f"cancel_{button_key}")
        if cancel_button:
            st.session_state.cancel_event.set()
    
    # Create a container for streaming content
    content_container = st.container()
    with content_container:
        content_placeholder = st.empty()
        accumulated_content = ""
        content_saved = False
        
        try:
            # Stream the content using OpenRouter Direct Upload
            for chunk in generate_specific_content_streaming(
                content_type,
                pdf_bytes, 
                pdf_filename, 
                selected_grade,
                model_progression, 
                subject_type,
                word_limits,
                use_openrouter_method=True
            ):
                if st.session_state.cancel_event.is_set():
                    st.warning("⚠️ Generation cancelled by user.")
                    break
                
                accumulated_content += chunk
                
                # CRITICAL: Auto-save during streaming to prevent loss
                auto_save_during_streaming(content_type, accumulated_content)
                
                # Update the placeholder with accumulated content
                with content_placeholder.container():
                    st.markdown(f"### Generated {content_type.title()} Content:")
                    st.markdown(accumulated_content + " ⏳")
            
            # Always try to save content if we have any, regardless of completion status
            if accumulated_content:
                # CRITICAL: Final save with all protection strategies
                save_content_safely(content_type, accumulated_content)
                
                with content_placeholder.container():
                    if st.session_state.cancel_event.is_set():
                        st.markdown(f"### ⚠️ {content_type.title()} Content (Cancelled - Partial):")
                    else:
                        st.markdown(f"### ✅ {content_type.title()} Content (Complete):")
                    st.markdown(accumulated_content)
                
                # Determine success message
                if st.session_state.cancel_event.is_set():
                    return accumulated_content, "Partial content saved (generation cancelled by user)"
                else:
                    return accumulated_content, "Generated successfully using streaming!"
            else:
                return None, "No content generated"
                
        except Exception as e:
            st.error(f"❌ Error during streaming: {e}")
            # Always try to save any content we managed to generate
            if accumulated_content:
                st.info("💾 Saving partial content despite error...")
                
                # CRITICAL: Save partial content with protection
                save_content_safely(content_type, accumulated_content)
                
                with content_placeholder.container():
                    st.markdown(f"### ⚠️ {content_type.title()} Content (Partial - Error Occurred):")
                    st.markdown(accumulated_content)
                return accumulated_content, f"Partial content saved due to error: {str(e)}"
            return None, f"Error: {str(e)}"

# --- Hybrid Content Expansion System ---
def parse_content_sections(content: str) -> List[Dict[str, Any]]:
    """Automatically detect expandable sections in generated content"""
    sections = []
    
    if not content:
        return sections
    
    # Split content into lines for processing
    lines = content.split('\n')
    current_section = ""
    section_type = "paragraph"
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Detect different section types
        if re.match(r'^#{1,6}\s+(.+)$', line):  # Headings
            if current_section:
                sections.append({
                    'type': section_type,
                    'text': current_section.strip(),
                    'expandable': True,
                    'line_start': max(0, i-10),
                    'line_end': min(len(lines), i+10)
                })
            current_section = line
            section_type = 'heading'
            
        elif re.match(r'^\*\*([^*]+)\*\*', line):  # Bold concepts
            if current_section:
                sections.append({
                    'type': section_type,
                    'text': current_section.strip(),
                    'expandable': True,
                    'line_start': max(0, i-5),
                    'line_end': min(len(lines), i+15)
                })
            current_section = line
            section_type = 'concept'
            
        elif re.match(r'^[-*+]\s+(.+)$', line):  # List items
            if section_type != 'list':
                if current_section:
                    sections.append({
                        'type': section_type,
                        'text': current_section.strip(),
                        'expandable': True,
                        'line_start': max(0, i-5),
                        'line_end': min(len(lines), i+10)
                    })
                current_section = line
                section_type = 'list'
            else:
                current_section += "\n" + line
                
        elif len(line) > 50:  # Regular paragraphs
            if section_type in ['heading', 'concept'] and current_section:
                current_section += "\n" + line
            else:
                if current_section and section_type != 'paragraph':
                    sections.append({
                        'type': section_type,
                        'text': current_section.strip(),
                        'expandable': True,
                        'line_start': max(0, i-5),
                        'line_end': min(len(lines), i+10)
                    })
                if section_type != 'paragraph':
                    current_section = line
                    section_type = 'paragraph'
                else:
                    current_section += "\n" + line
    
    # Add the last section
    if current_section:
        sections.append({
            'type': section_type,
            'text': current_section.strip(),
            'expandable': True,
            'line_start': 0,
            'line_end': len(lines)
        })
    
    return sections

def expand_text_with_ai(selected_text: str, expansion_type: str, context: str, content_type: str, grade_level: str, subject_type: str) -> str:
    """Generate expanded content for selected text using AI"""
    
    expansion_prompts = {
        'detail': "Provide more detailed explanation and depth",
        'examples': "Add relevant examples, case studies, and practical applications",
        'activities': "Add hands-on activities, experiments, and interactive exercises",
        'simplify': "Make the explanation simpler and clearer for students",
        'questions': "Add thought-provoking questions and assessments",
        'connections': "Add connections to other concepts and real-world applications"
    }
    
    prompt = f"""You are an expert educational content developer for CBSE {grade_level} curriculum.

TASK: Expand the selected educational content with {expansion_prompts.get(expansion_type, 'more detail')}.

CONTEXT:
- Content Type: {content_type}
- Grade Level: {grade_level} (CBSE)
- Subject: {subject_type}
- Selected Text: "{selected_text}"
- Surrounding Context: "{context[:500]}..."

EXPANSION TYPE: {expansion_type.upper()}

REQUIREMENTS:
1. Keep the same educational tone and CBSE alignment
2. Make content appropriate for {grade_level} students
3. Maintain consistency with existing content
4. Target expansion: 2-3x the original length
5. Use clear, engaging language
6. Include proper formatting (markdown)

EXPANDED CONTENT:"""
    
    try:
        # Create messages for AI
        messages = [{"role": "user", "content": prompt}]
        
        # Generate expansion
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": YOUR_SITE_URL,
                "X-Title": YOUR_SITE_NAME,
            },
            model=MODEL_NAME,
            messages=messages,
            max_tokens=8192,
            temperature=0.4,
        )
        
        return completion.choices[0].message.content
        
    except Exception as e:
        return f"Error generating expansion: {str(e)}"

def display_section_expander(sections: List[Dict[str, Any]], content_type: str, grade_level: str, subject_type: str):
    """Display expandable sections with expansion buttons"""
    
    st.subheader("🔍 Section-by-Section Expansion")
    st.markdown("*Click the expand button next to any section you want to develop further.*")
    
    for i, section in enumerate(sections):
        # Create container for each section
        with st.container():
            col1, col2 = st.columns([5, 1])
            
            with col1:
                # Display section based on type
                if section['type'] == 'heading':
                    st.markdown(section['text'])
                elif section['type'] == 'concept':
                    st.markdown(section['text'])
                else:
                    # Truncate long paragraphs for display
                    display_text = section['text'][:200] + "..." if len(section['text']) > 200 else section['text']
                    st.markdown(display_text)
            
            with col2:
                # Expansion button
                if st.button("🔍 Expand", key=f"expand_section_{i}", help=f"Expand this {section['type']}"):
                    # Show expansion options
                    st.session_state[f"show_expansion_options_{i}"] = True
                    st.rerun()
            
            # Show expansion options if button was clicked
            if st.session_state.get(f"show_expansion_options_{i}", False):
                with st.container():
                    st.markdown("**Choose expansion type:**")
                    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
                    
                    expansion_type = None
                    if exp_col1.button("📝 More Detail", key=f"detail_{i}"):
                        expansion_type = "detail"
                    if exp_col2.button("💡 Add Examples", key=f"examples_{i}"):
                        expansion_type = "examples"
                    if exp_col3.button("🎯 Add Activities", key=f"activities_{i}"):
                        expansion_type = "activities"
                    if exp_col4.button("📖 Simplify", key=f"simplify_{i}"):
                        expansion_type = "simplify"
                    
                    if expansion_type:
                        with st.spinner(f"🧠 Expanding section with {expansion_type}..."):
                            expanded_content = expand_text_with_ai(
                                selected_text=section['text'],
                                expansion_type=expansion_type,
                                context=section['text'],  # For now, use section itself as context
                                content_type=content_type,
                                grade_level=grade_level,
                                subject_type=subject_type
                            )
                            
                            st.session_state[f"expanded_content_{i}"] = expanded_content
                            st.session_state[f"show_expansion_options_{i}"] = False
                            st.rerun()
            
            # Show expanded content if available
            if st.session_state.get(f"expanded_content_{i}"):
                with st.expander("✨ Expanded Content", expanded=True):
                    st.markdown(st.session_state[f"expanded_content_{i}"])
                    
                    # Option to replace original content
                    if st.button("🔄 Replace Original", key=f"replace_{i}"):
                        # Here you could update the original content
                        st.success("Content replacement functionality can be added here!")
            
            st.divider()

def display_manual_text_expander(original_content: str, content_type: str, grade_level: str, subject_type: str):
    """Allow users to manually specify text for expansion"""
    
    st.subheader("🎯 Manual Text Expansion")
    st.markdown("*Copy and paste any specific text from your content that you want to expand.*")
    
    # User input for text selection
    selected_text = st.text_area(
        "Paste the specific text you want to expand:",
        height=100,
        placeholder="Example: 'Current Concepts' or 'Mathematical explanation' or any specific paragraph...",
        key="manual_text_input"
    )
    
    if selected_text.strip():
        # Expansion type selection
        st.markdown("**Choose how to expand this text:**")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        exp_col4, exp_col5, exp_col6 = st.columns(3)
        
        expansion_type = None
        if exp_col1.button("📝 More Detail", key="manual_detail"):
            expansion_type = "detail"
        if exp_col2.button("💡 Add Examples", key="manual_examples"):
            expansion_type = "examples"
        if exp_col3.button("🎯 Add Activities", key="manual_activities"):
            expansion_type = "activities"
        if exp_col4.button("📖 Simplify", key="manual_simplify"):
            expansion_type = "simplify"
        if exp_col5.button("❓ Add Questions", key="manual_questions"):
            expansion_type = "questions"
        if exp_col6.button("🔗 Add Connections", key="manual_connections"):
            expansion_type = "connections"
        
        if expansion_type:
            with st.spinner(f"🧠 Expanding your text with {expansion_type}..."):
                # Find context around the selected text
                context = ""
                if selected_text in original_content:
                    start_idx = original_content.find(selected_text)
                    context_start = max(0, start_idx - 200)
                    context_end = min(len(original_content), start_idx + len(selected_text) + 200)
                    context = original_content[context_start:context_end]
                
                expanded_content = expand_text_with_ai(
                    selected_text=selected_text,
                    expansion_type=expansion_type,
                    context=context,
                    content_type=content_type,
                    grade_level=grade_level,
                    subject_type=subject_type
                )
                
                st.markdown("### ✨ Expanded Content:")
                st.markdown(expanded_content)
                
                # Option to save expanded content
                if st.button("💾 Save Expansion", key="save_manual_expansion"):
                    # Store in session state for later use
                    if 'saved_expansions' not in st.session_state:
                        st.session_state.saved_expansions = []
                    
                    st.session_state.saved_expansions.append({
                        'original': selected_text,
                        'expanded': expanded_content,
                        'type': expansion_type,
                        'timestamp': time.time()
                    })
                    st.success("✅ Expansion saved! You can view all saved expansions below.")

def display_global_content_expander(original_content: str, content_type: str, grade_level: str, subject_type: str):
    """Global content expansion options"""
    
    st.subheader("🚀 Global Content Enhancement")
    st.markdown("*Enhance the entire content with specific improvements.*")
    
    col1, col2, col3 = st.columns(3)
    
    global_action = None
    if col1.button("📏 Make Content Longer", key="global_longer"):
        global_action = "longer"
    if col2.button("🎯 Add More Activities", key="global_activities"):
        global_action = "activities"
    if col3.button("💡 Add More Examples", key="global_examples"):
        global_action = "examples"
    
    if global_action:
        with st.spinner(f"🧠 Enhancing entire content..."):
            if global_action == "longer":
                prompt = f"""Make this {content_type} content significantly longer and more detailed for {grade_level} CBSE students.
                
Original Content:
{original_content}

Add more depth, explanations, and comprehensive coverage while maintaining the same structure and educational quality."""
                
            elif global_action == "activities":
                prompt = f"""Add more hands-on activities, exercises, and interactive elements throughout this {content_type} content for {grade_level} CBSE students.

Original Content:
{original_content}

Integrate practical activities that reinforce learning and engage students actively."""
                
            elif global_action == "examples":
                prompt = f"""Add more real-world examples, case studies, and practical applications throughout this {content_type} content for {grade_level} CBSE students.

Original Content:
{original_content}

Include diverse examples that help students understand concepts better."""
            
            try:
                messages = [{"role": "user", "content": prompt}]
                
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": YOUR_SITE_URL,
                        "X-Title": YOUR_SITE_NAME,
                    },
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=16384,
                    temperature=0.4,
                )
                
                enhanced_content = completion.choices[0].message.content
                
                st.markdown("### ✨ Enhanced Content:")
                st.markdown(enhanced_content)
                
                # Option to replace original content
                col1, col2 = st.columns(2)
                if col1.button("🔄 Replace Original Content", key=f"replace_global_{global_action}"):
                    # Update the session state with enhanced content
                    if content_type == "chapter":
                        st.session_state.chapter_content = enhanced_content
                    elif content_type == "exercises":
                        st.session_state.exercises = enhanced_content
                    elif content_type == "skills":
                        st.session_state.skill_activities = enhanced_content
                    elif content_type == "art":
                        st.session_state.art_learning = enhanced_content
                    
                    st.success("✅ Original content replaced with enhanced version!")
                    st.rerun()
                
                if col2.button("💾 Save as New Version", key=f"save_global_{global_action}"):
                    # Save as a new version
                    st.session_state[f"{content_type}_enhanced_{global_action}"] = enhanced_content
                    st.success("✅ Enhanced content saved as new version!")
                
            except Exception as e:
                st.error(f"Error enhancing content: {str(e)}")

def hybrid_content_expander(content: str, content_type: str, grade_level: str, subject_type: str):
    """Complete hybrid content expansion system"""
    
    if not content:
        st.warning("No content available for expansion.")
        return
    
    st.markdown("---")
    st.header("✨ Content Expansion Studio")
    st.markdown("*Enhance your generated content with AI-powered expansions*")
    
    # Parse content into sections
    sections = parse_content_sections(content)
    
    # Tab interface for different expansion methods
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Auto-Sections", "🎯 Manual Select", "🚀 Global Enhance", "💾 Saved Expansions"])
    
    with tab1:
        if sections:
            display_section_expander(sections, content_type, grade_level, subject_type)
        else:
            st.info("No expandable sections detected. Try the Manual Select tab to expand specific text.")
    
    with tab2:
        display_manual_text_expander(content, content_type, grade_level, subject_type)
    
    with tab3:
        display_global_content_expander(content, content_type, grade_level, subject_type)
    
    with tab4:
        st.subheader("💾 Your Saved Expansions")
        if 'saved_expansions' in st.session_state and st.session_state.saved_expansions:
            for i, expansion in enumerate(st.session_state.saved_expansions):
                with st.expander(f"Expansion {i+1}: {expansion['type'].title()}", expanded=False):
                    st.markdown("**Original Text:**")
                    st.markdown(expansion['original'][:200] + "..." if len(expansion['original']) > 200 else expansion['original'])
                    st.markdown("**Expanded Version:**")
                    st.markdown(expansion['expanded'])
                    
                    if st.button(f"🗑️ Delete", key=f"delete_expansion_{i}"):
                        st.session_state.saved_expansions.pop(i)
                        st.rerun()
        else:
            st.info("No saved expansions yet. Use the other tabs to create expansions.")

# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("📚 EeeBee Content Development Suite ✨ (OpenRouter Edition)")

st.markdown("""
Welcome to the EeeBee Content Development Suite powered by Claude via OpenRouter! 
Choose between improving existing chapters or chatting with EeeBee for content assistance.
""")

# Create tabs for different functionalities
tab1, tab2 = st.tabs(["📚 Chapter Improver", "💬 Content Chat with EeeBee"])

with tab1:
    st.header("📚 Book Chapter Improver Tool")
    st.markdown("""
    Upload your book chapter in PDF format. This tool will analyze it using EeeBee (Claude)
    based on the 'Model Chapter Progression and Elements' and suggest improvements.
    Select which part of the content you want to generate.
    
    ✨ **New Features**: 
    - **Content Protection**: Your content is automatically saved with multiple backups to prevent loss
    - **Expand Content**: Use the **"Expand Content"** buttons to enhance any generated content with:
      - **Auto-Section Detection**: Click specific sections to expand
      - **Manual Text Selection**: Paste any text you want to develop further  
      - **Global Enhancement**: Make entire content longer or add more examples/activities
    
    💾 **Content Status**: Check the sidebar to monitor your content safety and recovery options.
    """)

    # Grade Level Selector
    grade_options = [f"Grade {i}" for i in range(1, 13)] # Grades 1-12
    selected_grade = st.selectbox("Select Target Grade Level (CBSE):", grade_options, index=8, key="grade_selector_tab1") # Default to Grade 9

    # Subject Type Selector
    subject_type = st.selectbox(
        "Select Subject Type:",
        ["Science (Uses Model Chapter Progression)", "Mathematics", "Mathematics Primary (Classes 1-5)", "Science & E.V.S. (Classes 1-2)", "Science & E.V.S. (Classes 3-5)", "Computer Science"],
        help="Choose the appropriate subject type based on your needs. Science EVS options are specialized for primary grades.",
        key="subject_selector_tab1"
    )

    # Word Limit Controls
    st.subheader("📝 Content Length Settings")
    with st.expander("Configure Word Limits for Each Section", expanded=False):
        if subject_type == "Mathematics Primary (Classes 1-5)":
            # Special word limits for Primary Mathematics
            st.markdown("**Mathematics Primary (Classes 1-5) Structure**")
            col1, col2 = st.columns(2)
            
            with col1:
                hook_words = st.number_input("Chapter Opener - The Hook (words)", min_value=100, value=150, step=10, key="primary_hook_words")
                discover_words = st.number_input("Let's Discover - Concept & Practice (words)", min_value=1000, value=1500, step=100, key="primary_discover_words")
                activity_words = st.number_input("Activity Zone - Hands-on (words)", min_value=200, value=300, step=25, key="primary_activity_words")
            
            with col2:
                recap_words = st.number_input("Quick Recap - Revision (words)", min_value=150, value=200, step=25, key="primary_recap_words")
                exercises_words = st.number_input("Exercises (words)", min_value=500, value=800, step=50, key="primary_exercises_words")
            
            # Store word limits for primary mathematics
            st.session_state.word_limits = {
                'hook': hook_words,
                'discover': discover_words,
                'activity': activity_words,
                'recap': recap_words,
                'exercises': exercises_words
            }
        elif subject_type == "Science & E.V.S. (Classes 1-2)":
            # Special word limits for Science EVS Classes 1-2
            st.markdown("**Science & E.V.S. (Classes 1-2) Play-Based Structure**")
            col1, col2 = st.columns(2)
            
            with col1:
                opener_words = st.number_input("Chapter Opener - Story and Wonder (words)", min_value=100, value=200, step=25, key="evs12_opener_words")
                activity_words = st.number_input("Let's Play & Do - Per Activity (words)", min_value=150, value=250, step=25, key="evs12_activity_words")
                concept_words = st.number_input("Concept Connect - Per Concept (words)", min_value=100, value=200, step=25, key="evs12_concept_words")
            
            with col2:
                closer_words = st.number_input("Chapter Closer - Learning Together (words)", min_value=100, value=150, step=25, key="evs12_closer_words")
                activities_words = st.number_input("Play-Based Activities Total (words)", min_value=400, value=600, step=50, key="evs12_activities_words")
            
            # Store word limits for Science EVS Classes 1-2
            st.session_state.word_limits = {
                'opener': opener_words,
                'activity': activity_words,
                'concept': concept_words,
                'closer': closer_words,
                'activities': activities_words
            }
        elif subject_type == "Science & E.V.S. (Classes 3-5)":
            # Special word limits for Science EVS Classes 3-5
            st.markdown("**Science & E.V.S. (Classes 3-5) Inquiry-Based Structure**")
            col1, col2 = st.columns(2)
            
            with col1:
                opener_words = st.number_input("Chapter Opener Page (words)", min_value=200, value=300, step=25, key="evs35_opener_words")
                exploration_words = st.number_input("Let's Uncover the Secrets (words)", min_value=1500, value=2000, step=100, key="evs35_exploration_words")
                project_words = st.number_input("Capstone Project (words)", min_value=300, value=400, step=50, key="evs35_project_words")
            
            with col2:
                summary_words = st.number_input("Summary & Revision Tools (words)", min_value=200, value=250, step=25, key="evs35_summary_words")
                exercises_words = st.number_input("End-of-Chapter Exercises (words)", min_value=500, value=600, step=50, key="evs35_exercises_words")
            
            # Store word limits for Science EVS Classes 3-5
            st.session_state.word_limits = {
                'opener': opener_words,
                'exploration': exploration_words,
                'project': project_words,
                'summary': summary_words,
                'exercises': exercises_words
            }
        else:
            # Standard word limits for other subjects
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Core Sections**")
                hook_words = st.number_input("Hook (words)", min_value=20, value=80, step=10, key="hook_words")
                learning_outcome_words = st.number_input("Learning Outcome (words)", min_value=30, value=70, step=10, key="learning_outcome_words")
                real_world_words = st.number_input("Real World Connection (words)", min_value=30, value=50, step=10, key="real_world_words")
                previous_class_words = st.number_input("Previous Class Concept (words)", min_value=30, value=100, step=10, key="previous_class_words")
                history_words = st.number_input("History (words)", min_value=50, value=100, step=10, key="history_words")
            
            with col2:
                st.markdown("**Main Content**")
                current_concepts_words = st.number_input("Current Concepts (words)", min_value=500, value=1200, step=100, key="current_concepts_words")
                summary_words = st.number_input("Summary (words)", min_value=300, value=700, step=50, key="summary_words")
                link_learn_words = st.number_input("Link and Learn Questions (words)", min_value=100, value=250, step=25, key="link_learn_words")
                image_based_words = st.number_input("Image Based Questions (words)", min_value=100, value=250, step=25, key="image_based_words")
            
            with col3:
                st.markdown("**Activities & Exercises**")
                exercises_words = st.number_input("Exercise Questions (words)", min_value=300, value=800, step=50, key="exercises_words")
                skill_activity_words = st.number_input("Skill Activities (words)", min_value=200, value=400, step=50, key="skill_activity_words")
                stem_activity_words = st.number_input("STEM Activities (words)", min_value=200, value=400, step=50, key="stem_activity_words")
                art_learning_words = st.number_input("Art Learning (words)", min_value=200, value=400, step=50, key="art_learning_words")

            # Store word limits in session state
            st.session_state.word_limits = {
                'hook': hook_words,
                'learning_outcome': learning_outcome_words,
                'real_world': real_world_words,
                'previous_class': previous_class_words,
                'history': history_words,
                'current_concepts': current_concepts_words,
                'summary': summary_words,
                'link_learn': link_learn_words,
                'image_based': image_based_words,
                'exercises': exercises_words,
                'skill_activity': skill_activity_words,
                'stem_activity': stem_activity_words,
                'art_learning': art_learning_words
            }

    # Analysis Method Selector
    analysis_method = st.radio(
        "Choose Analysis Method:",
        ["Standard (Full Document)", "Chunked (For Complex Documents)"],
        help="Use 'Chunked' method for very large documents or if you encounter errors with the standard method.",
        key="analysis_method_tab1"
    )

    # Using OpenRouter Direct PDF Upload (most reliable method)
    st.info("📄 **PDF Processing:** Using OpenRouter Direct Upload for optimal performance with all file sizes and types")

    # Streaming Mode Toggle
    use_streaming = st.checkbox(
        "Enable Streaming Mode",
        value=True,
        help="Stream responses in real-time as they are generated. You can cancel generation at any time.",
        key="streaming_mode_tab1"
    )

    # Load Model Chapter Progression
    model_progression = load_model_chapter_progression()

    # Initialize session state for content persistence (MOVED OUTSIDE FILE UPLOAD CONDITION)
    if 'chapter_content' not in st.session_state:
        st.session_state.chapter_content = None
    if 'exercises' not in st.session_state:
        st.session_state.exercises = None
    if 'skill_activities' not in st.session_state:
        st.session_state.skill_activities = None
    if 'art_learning' not in st.session_state:
        st.session_state.art_learning = None
    
    # Auto-recover any lost content on startup
    verify_and_recover_all_content()
    
    # Display content protection status
    display_content_status()

    if model_progression:
        st.sidebar.subheader("Model Chapter Progression:")
        st.sidebar.text_area("Model Details", model_progression, height=300, disabled=True)

        # Display previously generated content (MOVED OUTSIDE FILE UPLOAD CONDITION)
        col_header1, col_header2 = st.columns([4, 1])
        with col_header1:
            st.subheader("📋 Previously Generated Content")
        with col_header2:
            if st.button("🗑️ Clear All Content", key="clear_all_content", help="Clear all generated content from session"):
                st.session_state.chapter_content = None
                st.session_state.exercises = None
                st.session_state.skill_activities = None
                st.session_state.art_learning = None
                st.success("✅ All content cleared!")
                st.rerun()
        
        prev_col1, prev_col2, prev_col3, prev_col4 = st.columns(4)
        
        with prev_col1:
            if st.session_state.chapter_content:
                with st.expander("📖 Chapter Content Available", expanded=False):
                    st.markdown(st.session_state.chapter_content[:500] + "..." if len(st.session_state.chapter_content) > 500 else st.session_state.chapter_content)
                    
                    col_dl, col_expand = st.columns(2)
                    with col_dl:
                        doc = create_word_document(st.session_state.chapter_content)
                        doc_io = io.BytesIO()
                        doc.save(doc_io)
                        doc_io.seek(0)
                        st.download_button(
                            label="📥 Download",
                            data=doc_io,
                            file_name="chapter_content.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="prev_download_chapter"
                        )
                    with col_expand:
                        if st.button("✨ Expand Content", key="expand_chapter_btn"):
                            st.session_state.show_chapter_expander = True
                            st.rerun()
            else:
                st.info("📖 No chapter content generated yet")
        
        with prev_col2:
            if st.session_state.exercises:
                with st.expander("📝 Exercises Available", expanded=False):
                    st.markdown(st.session_state.exercises[:500] + "..." if len(st.session_state.exercises) > 500 else st.session_state.exercises)
                    
                    col_dl, col_expand = st.columns(2)
                    with col_dl:
                        doc = create_word_document(st.session_state.exercises)
                        doc_io = io.BytesIO()
                        doc.save(doc_io)
                        doc_io.seek(0)
                        st.download_button(
                            label="📥 Download",
                            data=doc_io,
                            file_name="exercises.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="prev_download_exercises"
                        )
                    with col_expand:
                        if st.button("✨ Expand Content", key="expand_exercises_btn"):
                            st.session_state.show_exercises_expander = True
                            st.rerun()
            else:
                st.info("📝 No exercises generated yet")
        
        with prev_col3:
            if st.session_state.skill_activities:
                with st.expander("🛠️ Skills Available", expanded=False):
                    st.markdown(st.session_state.skill_activities[:500] + "..." if len(st.session_state.skill_activities) > 500 else st.session_state.skill_activities)
                    
                    col_dl, col_expand = st.columns(2)
                    with col_dl:
                        doc = create_word_document(st.session_state.skill_activities)
                        doc_io = io.BytesIO()
                        doc.save(doc_io)
                        doc_io.seek(0)
                        st.download_button(
                            label="📥 Download",
                            data=doc_io,
                            file_name="skill_activities.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="prev_download_skills"
                        )
                    with col_expand:
                        if st.button("✨ Expand Content", key="expand_skills_btn"):
                            st.session_state.show_skills_expander = True
                            st.rerun()
            else:
                st.info("🛠️ No skill activities generated yet")
        
        with prev_col4:
            if st.session_state.art_learning:
                with st.expander("🎨 Art Learning Available", expanded=False):
                    st.markdown(st.session_state.art_learning[:500] + "..." if len(st.session_state.art_learning) > 500 else st.session_state.art_learning)
                    
                    col_dl, col_expand = st.columns(2)
                    with col_dl:
                        doc = create_word_document(st.session_state.art_learning)
                        doc_io = io.BytesIO()
                        doc.save(doc_io)
                        doc_io.seek(0)
                        st.download_button(
                            label="📥 Download",
                            data=doc_io,
                            file_name="art_learning.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="prev_download_art"
                        )
                    with col_expand:
                        if st.button("✨ Expand Content", key="expand_art_btn"):
                            st.session_state.show_art_expander = True
                            st.rerun()
            else:
                st.info("🎨 No art learning generated yet")

        # Content Expansion Displays (when expand buttons are clicked)
        if st.session_state.get('show_chapter_expander', False):
            hybrid_content_expander(
                st.session_state.chapter_content, 
                "chapter", 
                selected_grade, 
                subject_type.replace(" (Uses Model Chapter Progression)", "")
            )
            if st.button("❌ Close Expander", key="close_chapter_expander"):
                st.session_state.show_chapter_expander = False
                st.rerun()
        
        if st.session_state.get('show_exercises_expander', False):
            hybrid_content_expander(
                st.session_state.exercises, 
                "exercises", 
                selected_grade, 
                subject_type.replace(" (Uses Model Chapter Progression)", "")
            )
            if st.button("❌ Close Expander", key="close_exercises_expander"):
                st.session_state.show_exercises_expander = False
                st.rerun()
        
        if st.session_state.get('show_skills_expander', False):
            hybrid_content_expander(
                st.session_state.skill_activities, 
                "skills", 
                selected_grade, 
                subject_type.replace(" (Uses Model Chapter Progression)", "")
            )
            if st.button("❌ Close Expander", key="close_skills_expander"):
                st.session_state.show_skills_expander = False
                st.rerun()
        
        if st.session_state.get('show_art_expander', False):
            hybrid_content_expander(
                st.session_state.art_learning, 
                "art", 
                selected_grade, 
                subject_type.replace(" (Uses Model Chapter Progression)", "")
            )
            if st.button("❌ Close Expander", key="close_art_expander"):
                st.session_state.show_art_expander = False
                st.rerun()

        uploaded_file_st = st.file_uploader("Upload your chapter (PDF only)", type="pdf", key="pdf_uploader_tab1")

        if uploaded_file_st is not None:
            st.info(f"Processing '{uploaded_file_st.name}' for {selected_grade}...")
            
            # Get PDF bytes for processing
            pdf_bytes = uploaded_file_st.getvalue()

            # Create columns for the buttons
            col1, col2 = st.columns(2)
            col3, col4 = st.columns(2)

            st.divider()
            
            st.subheader("🚀 Generate New Content")

            if subject_type == "Mathematics Primary (Classes 1-5)":
                # For primary mathematics, show chapter and exercises generation
                st.info("📘 **Mathematics Primary Mode**: For Classes 1-5, we provide specialized content generation designed for young learners.")
                
                # Show chapter and exercises buttons for primary mathematics
                prim_col1, prim_col2 = st.columns(2)
                
                with prim_col1:
                    generate_chapter = st.button("🔍 Generate Complete Mathematics Chapter", key="gen_primary_chapter")
                
                with prim_col2:
                    generate_exercises = st.button("📝 Generate Mathematics Exercises", key="gen_primary_exercises")
                
                generate_skills = False  
                generate_art = False
            elif subject_type == "Science & E.V.S. (Classes 1-2)":
                # For Science EVS Classes 1-2, show chapter and activities generation
                st.info("🌱 **Science & E.V.S. Classes 1-2**: Play-based learning approach for foundational stage. Activities are integrated within the chapter.")
                
                # Show chapter and activities buttons for Science EVS Classes 1-2
                evs12_col1, evs12_col2 = st.columns(2)
                
                with evs12_col1:
                    generate_chapter = st.button("🔍 Generate Play-Based Chapter", key="gen_evs12_chapter")
                
                with evs12_col2:
                    generate_exercises = st.button("🎮 Generate Play Activities", key="gen_evs12_activities")
                
                generate_skills = False  
                generate_art = False
            elif subject_type == "Science & E.V.S. (Classes 3-5)":
                # For Science EVS Classes 3-5, show chapter and exercises generation
                st.info("🔬 **Science & E.V.S. Classes 3-5**: Inquiry-based learning approach for preparatory stage. Skills and art activities are integrated within the chapter.")
                
                # Show chapter and exercises buttons for Science EVS Classes 3-5
                evs35_col1, evs35_col2 = st.columns(2)
                
                with evs35_col1:
                    generate_chapter = st.button("🔍 Generate Inquiry-Based Chapter", key="gen_evs35_chapter")
                
                with evs35_col2:
                    generate_exercises = st.button("📝 Generate Assessment Exercises", key="gen_evs35_exercises")
                
                generate_skills = False  
                generate_art = False
            else:
                # Standard buttons for other subjects
                # Generate Chapter Content Button
                generate_chapter = col1.button("🔍 Generate Chapter Content", key="gen_chapter")
                
                # Generate Exercises Button
                generate_exercises = col2.button("📝 Generate Exercises", key="gen_exercises")
                
                # Generate Skill Activities Button
                generate_skills = col3.button("🛠️ Generate Skill Activities", key="gen_skills")
                
                # Generate Art Learning Button
                generate_art = col4.button("🎨 Generate Art-Integrated Learning", key="gen_art")
            
            # Download All Button (outside columns)
            download_all = st.button("📥 Download Complete Chapter with All Elements", key="download_all")
            
            # Handle button clicks and content generation
            if generate_chapter:
                # Get word limits from session state
                word_limits = st.session_state.get('word_limits', {})
                
                with st.spinner(f"🧠 Generating Chapter Content for {selected_grade}..."):
                    if use_streaming:
                        # Initialize cancel event for streaming
                        st.session_state.cancel_event = Event()
                        
                        # Create cancel button and content container
                        cancel_col1, cancel_col2 = st.columns([5, 1])
                        with cancel_col2:
                            cancel_button = st.button("🛑 Cancel", key="cancel_chapter")
                            if cancel_button:
                                st.session_state.cancel_event.set()
                        
                        # Create container for streaming content
                        content_container = st.container()
                        with content_container:
                            content_placeholder = st.empty()
                            accumulated_content = ""
                            
                            try:
                                # Stream the content
                                for chunk in generate_specific_content_streaming(
                                    "chapter",
                                    pdf_bytes, 
                                    uploaded_file_st.name, 
                                    selected_grade,
                                    model_progression, 
                                    subject_type,
                                    word_limits,
                                    use_openrouter_method=True
                                ):
                                    if st.session_state.cancel_event.is_set():
                                        st.warning("⚠️ Generation cancelled by user.")
                                        break
                                    accumulated_content += chunk
                                    
                                    # CRITICAL: Auto-save during streaming to prevent loss
                                    auto_save_during_streaming("chapter_content", accumulated_content)
                                    
                                    # Update the placeholder with accumulated content (in a code block to preserve formatting)
                                    with content_placeholder.container():
                                        st.markdown("### Generated Chapter Content:")
                                        st.markdown(accumulated_content + " ⏳")
                                
                                # Always save content if we have any, regardless of completion status
                                if accumulated_content:
                                    st.session_state.chapter_content = accumulated_content
                                    
                                    # CRITICAL: Final save with all protection strategies
                                    save_content_safely("chapter_content", accumulated_content, selected_grade)
                                    
                                    with content_placeholder.container():
                                        if st.session_state.cancel_event.is_set():
                                            st.markdown("### ⚠️ Chapter Content (Cancelled - Partial):")
                                        else:
                                            st.markdown("### ✅ Chapter Content (Complete):")
                                        st.markdown(st.session_state.chapter_content)
                                    
                                    if st.session_state.cancel_event.is_set():
                                        st.warning("⚠️ Chapter Content partially generated (cancelled by user) but saved!")
                                    else:
                                        st.success(f"✅ Chapter Content generated successfully!")
                                    
                                    # Download button (available even for partial content)
                                    doc = create_word_document(st.session_state.chapter_content)
                                    doc_io = io.BytesIO()
                                    doc.save(doc_io)
                                    doc_io.seek(0)
                                    st.download_button(
                                        label="📥 Download Chapter Content as Word (.docx)",
                                        data=doc_io,
                                        file_name=f"chapter_content_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key="download_chapter_streaming"
                                    )
                                else:
                                    st.error("❌ No content was generated.")
                                    
                            except Exception as e:
                                st.error(f"❌ Error during streaming: {e}")
                                # Always save any partial content
                                if accumulated_content:
                                    st.info("💾 Saving partial content despite error...")
                                    st.session_state.chapter_content = accumulated_content
                                    
                                    # CRITICAL: Save partial content with protection
                                    save_content_safely("chapter_content", accumulated_content, selected_grade)
                                    
                                    with content_placeholder.container():
                                        st.markdown("### ⚠️ Chapter Content (Partial - Error Occurred):")
                                        st.markdown(st.session_state.chapter_content)
                                    
                                    # Download button for partial content
                                    doc = create_word_document(st.session_state.chapter_content)
                                    doc_io = io.BytesIO()
                                    doc.save(doc_io)
                                    doc_io.seek(0)
                                    st.download_button(
                                        label="📥 Download Partial Chapter Content as Word (.docx)",
                                        data=doc_io,
                                        file_name=f"partial_chapter_content_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key="download_chapter_partial"
                                    )
                    else:
                        # Use non-streaming approach
                        content, message = generate_specific_content(
                            "chapter", 
                            pdf_bytes, 
                            uploaded_file_st.name, 
                            selected_grade, 
                            model_progression, 
                            subject_type, 
                            word_limits,
                            use_chunked=(analysis_method == "Chunked (For Complex Documents)"), 
                            use_openrouter_method=True
                        )
                        if content:
                            st.session_state.chapter_content = content
                            
                            # CRITICAL: Save content with protection
                            save_content_safely("chapter_content", content, selected_grade)
                            
                            st.success(f"✅ Chapter Content generated successfully! {message}")
                            st.subheader("📖 Chapter Content:")
                            with st.expander("View Chapter Content", expanded=True):
                                st.markdown(st.session_state.chapter_content)
                            
                            # Download and Expand buttons
                            dl_col, expand_col = st.columns(2)
                            with dl_col:
                                doc = create_word_document(st.session_state.chapter_content)
                                doc_io = io.BytesIO()
                                doc.save(doc_io)
                                doc_io.seek(0)
                                st.download_button(
                                    label="📥 Download Chapter Content as Word (.docx)",
                                    data=doc_io,
                                    file_name=f"chapter_content_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key="download_chapter_standard"
                                )
                            with expand_col:
                                if st.button("✨ Expand This Content", key="expand_new_chapter"):
                                    st.session_state.show_new_chapter_expander = True
                                    st.rerun()
                        
                        # Show expander for newly generated content
                        if st.session_state.get('show_new_chapter_expander', False):
                            hybrid_content_expander(
                                st.session_state.chapter_content, 
                                "chapter", 
                                selected_grade, 
                                subject_type.replace(" (Uses Model Chapter Progression)", "")
                            )
                            if st.button("❌ Close Expander", key="close_new_chapter_expander"):
                                st.session_state.show_new_chapter_expander = False
                                st.rerun()
                        else:
                            st.error(f"❌ Failed to generate Chapter Content: {message}")
            
            if generate_exercises:
                # Get word limits from session state
                word_limits = st.session_state.get('word_limits', {})
                
                with st.spinner(f"🧠 Generating Exercises for {selected_grade}..."):
                    if use_streaming:
                        content, message = handle_streaming_generation(
                            "exercises", pdf_bytes, uploaded_file_st.name, selected_grade, 
                            model_progression, subject_type, word_limits, "exercises"
                        )
                        if content:
                            st.session_state.exercises = content
                            st.success(f"✅ Exercises generated successfully! {message}")
                            
                            # Download button
                            doc = create_word_document(st.session_state.exercises)
                            doc_io = io.BytesIO()
                            doc.save(doc_io)
                            doc_io.seek(0)
                            st.download_button(
                                label="📥 Download Exercises as Word (.docx)",
                                data=doc_io,
                                file_name=f"exercises_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="download_exercises_streaming"
                            )
                        else:
                            st.error(f"❌ Failed to generate Exercises: {message}")
                    else:
                        content, message = generate_specific_content(
                            "exercises", 
                            pdf_bytes, 
                            uploaded_file_st.name, 
                            selected_grade, 
                            model_progression, 
                            subject_type, 
                            word_limits,
                            use_chunked=(analysis_method == "Chunked (For Complex Documents)"), 
                            use_openrouter_method=True
                        )
                        if content:
                            st.session_state.exercises = content
                            
                            # CRITICAL: Save content with protection
                            save_content_safely("exercises", content, selected_grade)
                            
                            st.success(f"✅ Exercises generated successfully! {message}")
                            st.subheader("📝 Exercises:")
                            with st.expander("View Exercises", expanded=True):
                                st.markdown(st.session_state.exercises)
                            
                            # Download and Expand buttons
                            dl_col, expand_col = st.columns(2)
                            with dl_col:
                                doc = create_word_document(st.session_state.exercises)
                                doc_io = io.BytesIO()
                                doc.save(doc_io)
                                doc_io.seek(0)
                                st.download_button(
                                    label="📥 Download Exercises as Word (.docx)",
                                    data=doc_io,
                                    file_name=f"exercises_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key="download_exercises_standard"
                                )
                            with expand_col:
                                if st.button("✨ Expand This Content", key="expand_new_exercises"):
                                    st.session_state.show_new_exercises_expander = True
                                    st.rerun()
                        
                        # Show expander for newly generated exercises
                        if st.session_state.get('show_new_exercises_expander', False):
                            hybrid_content_expander(
                                st.session_state.exercises, 
                                "exercises", 
                                selected_grade, 
                                subject_type.replace(" (Uses Model Chapter Progression)", "")
                            )
                            if st.button("❌ Close Expander", key="close_new_exercises_expander"):
                                st.session_state.show_new_exercises_expander = False
                                st.rerun()
                        else:
                            st.error(f"❌ Failed to generate Exercises: {message}")
            
            if generate_skills:
                # Get word limits from session state
                word_limits = st.session_state.get('word_limits', {})
                
                with st.spinner(f"🧠 Generating Skill Activities for {selected_grade}..."):
                    if use_streaming:
                        content, message = handle_streaming_generation(
                            "skills", pdf_bytes, uploaded_file_st.name, selected_grade, 
                            model_progression, subject_type, word_limits, "skills"
                        )
                        if content:
                            st.session_state.skill_activities = content
                            st.success(f"✅ Skill Activities generated successfully! {message}")
                            
                            # Download button
                            doc = create_word_document(st.session_state.skill_activities)
                            doc_io = io.BytesIO()
                            doc.save(doc_io)
                            doc_io.seek(0)
                            st.download_button(
                                label="📥 Download Skill Activities as Word (.docx)",
                                data=doc_io,
                                file_name=f"skill_activities_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="download_skills_streaming"
                            )
                        else:
                            st.error(f"❌ Failed to generate Skill Activities: {message}")
                    else:
                        content, message = generate_specific_content(
                            "skills", 
                            pdf_bytes, 
                            uploaded_file_st.name, 
                            selected_grade, 
                            model_progression, 
                            subject_type, 
                            word_limits,
                            use_chunked=(analysis_method == "Chunked (For Complex Documents)"), 
                            use_openrouter_method=True
                        )
                        if content:
                            st.session_state.skill_activities = content
                            
                            # CRITICAL: Save content with protection
                            save_content_safely("skill_activities", content, selected_grade)
                            
                            st.success(f"✅ Skill Activities generated successfully! {message}")
                            st.subheader("🛠️ Skill Activities:")
                            with st.expander("View Skill Activities", expanded=True):
                                st.markdown(st.session_state.skill_activities)
                            
                            # Download and Expand buttons
                            dl_col, expand_col = st.columns(2)
                            with dl_col:
                                doc = create_word_document(st.session_state.skill_activities)
                                doc_io = io.BytesIO()
                                doc.save(doc_io)
                                doc_io.seek(0)
                                st.download_button(
                                    label="📥 Download Skill Activities as Word (.docx)",
                                    data=doc_io,
                                    file_name=f"skill_activities_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key="download_skills_standard"
                                )
                            with expand_col:
                                if st.button("✨ Expand This Content", key="expand_new_skills"):
                                    st.session_state.show_new_skills_expander = True
                                    st.rerun()
                        
                        # Show expander for newly generated skills
                        if st.session_state.get('show_new_skills_expander', False):
                            hybrid_content_expander(
                                st.session_state.skill_activities, 
                                "skills", 
                                selected_grade, 
                                subject_type.replace(" (Uses Model Chapter Progression)", "")
                            )
                            if st.button("❌ Close Expander", key="close_new_skills_expander"):
                                st.session_state.show_new_skills_expander = False
                                st.rerun()
                        else:
                            st.error(f"❌ Failed to generate Skill Activities: {message}")
            
            if generate_art:
                # Get word limits from session state
                word_limits = st.session_state.get('word_limits', {})
                
                with st.spinner(f"🧠 Generating Art-Integrated Learning for {selected_grade}..."):
                    if use_streaming:
                        content, message = handle_streaming_generation(
                            "art", pdf_bytes, uploaded_file_st.name, selected_grade, 
                            model_progression, subject_type, word_limits, "art"
                        )
                        if content:
                            st.session_state.art_learning = content
                            st.success(f"✅ Art-Integrated Learning generated successfully! {message}")
                            
                            # Download button
                            doc = create_word_document(st.session_state.art_learning)
                            doc_io = io.BytesIO()
                            doc.save(doc_io)
                            doc_io.seek(0)
                            st.download_button(
                                label="📥 Download Art-Integrated Learning as Word (.docx)",
                                data=doc_io,
                                file_name=f"art_learning_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="download_art_streaming"
                            )
                        else:
                            st.error(f"❌ Failed to generate Art-Integrated Learning: {message}")
                    else:
                        content, message = generate_specific_content(
                            "art", 
                            pdf_bytes, 
                            uploaded_file_st.name, 
                            selected_grade, 
                            model_progression, 
                            subject_type, 
                            word_limits,
                            use_chunked=(analysis_method == "Chunked (For Complex Documents)"), 
                            use_openrouter_method=True
                        )
                        if content:
                            st.session_state.art_learning = content
                            
                            # CRITICAL: Save content with protection
                            save_content_safely("art_learning", content, selected_grade)
                            
                            st.success(f"✅ Art-Integrated Learning generated successfully! {message}")
                            st.subheader("🎨 Art-Integrated Learning:")
                            with st.expander("View Art-Integrated Learning", expanded=True):
                                st.markdown(st.session_state.art_learning)
                            
                            # Download and Expand buttons
                            dl_col, expand_col = st.columns(2)
                            with dl_col:
                                doc = create_word_document(st.session_state.art_learning)
                                doc_io = io.BytesIO()
                                doc.save(doc_io)
                                doc_io.seek(0)
                                st.download_button(
                                    label="📥 Download Art-Integrated Learning as Word (.docx)",
                                    data=doc_io,
                                    file_name=f"art_learning_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key="download_art_standard"
                                )
                            with expand_col:
                                if st.button("✨ Expand This Content", key="expand_new_art"):
                                    st.session_state.show_new_art_expander = True
                                    st.rerun()
                        
                        # Show expander for newly generated art learning
                        if st.session_state.get('show_new_art_expander', False):
                            hybrid_content_expander(
                                st.session_state.art_learning, 
                                "art", 
                                selected_grade, 
                                subject_type.replace(" (Uses Model Chapter Progression)", "")
                            )
                            if st.button("❌ Close Expander", key="close_new_art_expander"):
                                st.session_state.show_new_art_expander = False
                                st.rerun()
                        else:
                            st.error(f"❌ Failed to generate Art-Integrated Learning: {message}")
            
            if download_all:
                # Combine all generated content (if any)
                all_content_parts = []
                
                if st.session_state.chapter_content:
                    all_content_parts.append("# CHAPTER CONTENT\n\n" + st.session_state.chapter_content)
                else:
                    st.warning("Chapter Content has not been generated yet.")
                
                if st.session_state.exercises:
                    all_content_parts.append("# EXERCISES\n\n" + st.session_state.exercises)
                else:
                    st.warning("Exercises have not been generated yet.")
                
                if st.session_state.skill_activities:
                    all_content_parts.append("# SKILL ACTIVITIES\n\n" + st.session_state.skill_activities)
                else:
                    st.warning("Skill Activities have not been generated yet.")
                
                if st.session_state.art_learning:
                    all_content_parts.append("# ART-INTEGRATED LEARNING\n\n" + st.session_state.art_learning)
                else:
                    st.warning("Art-Integrated Learning has not been generated yet.")
                
                if all_content_parts:
                    combined_content = "\n\n" + "\n\n".join(all_content_parts)
                    
                    # Create Word document with all content
                    doc = create_word_document(combined_content)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    
                    st.download_button(
                        label="📥 Download Complete Chapter with All Elements as Word (.docx)",
                        data=doc_io,
                        file_name=f"complete_chapter_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error("No content has been generated yet. Please generate at least one type of content first.")
    else:
        st.error("Failed to load the Model Chapter Progression. The tool cannot proceed without it.")

with tab2:
    st.header("💬 Content Chat with EeeBee")
    st.markdown("""
    Chat with EeeBee (powered by Claude) for content development assistance! Upload PDFs for context or ask questions directly.
    EeeBee can help with content creation, modification, curriculum alignment, and educational guidance.
    """)
    
    # Move chat settings to main area (above chat)
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Grade level for chat context
        chat_grade = st.selectbox(
            "Grade Level Context:", 
            [f"Grade {i}" for i in range(1, 13)], 
            index=8, 
            key="chat_grade"
        )
    
    with col2:
        # Subject context
        chat_subject = st.selectbox(
            "Subject Context:",
            ["Science Education", "Mathematics", "Mathematics Primary (Classes 1-5)", "Science & E.V.S. (Classes 1-2)", "Science & E.V.S. (Classes 3-5)", "Computer Science", "Social Studies", "English", "Hindi", "General Education", "Other"],
            key="chat_subject"
        )
    
    with col3:
        # Clear chat button
        if st.button("🗑️ Clear Chat History", key="clear_chat"):
            st.session_state.chat_messages = []
            st.session_state.chat_uploaded_files = []
            st.rerun()
    
    # PDF Upload for chat context
    st.subheader("📄 Upload Documents for Context")
    chat_uploaded_files = st.file_uploader(
        "Upload PDFs for EeeBee to reference:",
        type="pdf",
        accept_multiple_files=True,
        key="chat_pdf_uploader"
    )
    
    if chat_uploaded_files:
        st.session_state.chat_uploaded_files = chat_uploaded_files
        st.success(f"📄 {len(chat_uploaded_files)} PDF(s) uploaded successfully!")
        uploaded_files_info = ""
        for file in chat_uploaded_files:
            uploaded_files_info += f"• {file.name}\n"
        st.text(uploaded_files_info)
    
    st.divider()
    
    # Initialize chat session state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'chat_uploaded_files' not in st.session_state:
        st.session_state.chat_uploaded_files = []
    
    # Display chat messages in a container
    chat_container = st.container()
    
    with chat_container:
        # Display existing chat messages
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input at the bottom
    if prompt := st.chat_input("Ask EeeBee anything about content development..."):
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
        
        # Generate EeeBee response with streaming
        with chat_container:
            with st.chat_message("assistant"):
                # Create placeholder for streaming response
                response_placeholder = st.empty()
                response_text = ""
                
                try:
                    # Generate streaming response
                    for chunk in generate_chat_response_stream(
                        prompt, 
                        st.session_state.chat_messages, 
                        st.session_state.chat_uploaded_files,
                        chat_grade,
                        chat_subject
                    ):
                        response_text += chunk
                        response_placeholder.markdown(response_text + "▊")  # Add cursor effect
                    
                    # Remove cursor and show final response
                    response_placeholder.markdown(response_text)
                    
                    # Add assistant response to chat history
                    st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
                    
                except Exception as e:
                    error_message = f"I encountered an error: {str(e)}. Please try asking your question again."
                    response_placeholder.markdown(error_message)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_message})

st.sidebar.markdown("---")
st.sidebar.info("This app uses the Claude API via OpenRouter for AI-powered content analysis and generation.")

