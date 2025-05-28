import streamlit as st
# from openai import OpenAI # Removed
import google.generativeai as genai # Added
import fitz  # PyMuPDF - Still needed for initial validation or if we want to show images separately
from docx import Document
from PIL import Image
import io
import pathlib # Added

# --- Configuration ---
# OPENROUTER_API_KEY = "<YOUR_OPENROUTER_API_KEY_HERE>" # Removed
# YOUR_SITE_URL = "<YOUR_SITE_URL_HERE>" # Removed
# YOUR_SITE_NAME = "<YOUR_SITE_NAME_HERE>" # Removed

# Get Google API key from Streamlit secrets
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("""
    🔑 **Google API Key Not Found!**
    
    Please add your Google API key to Streamlit secrets:
    
    **For local development:**
    Create a `.streamlit/secrets.toml` file in your project directory with:
    ```toml
    GOOGLE_API_KEY = "your_google_api_key_here"
    ```
    
    **For Streamlit Cloud deployment:**
    1. Go to your app's settings in Streamlit Cloud
    2. Click on "Secrets" 
    3. Add the following:
    ```toml
    GOOGLE_API_KEY = "your_google_api_key_here"
    ```
    
    **How to get a Google API Key:**
    1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
    2. Create a new API key
    3. Copy the key and add it to your secrets
    """)
    st.stop()

# Initialize Google Gemini Client
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-2.5-pro-preview-05-06") # Updated model name
except Exception as e:
    st.error(f"Error configuring Google Gemini client: {e}")
    st.stop()


# --- Helper Functions (will be expanded) ---

def load_model_chapter_progression(file_path="Model Chapter Progression and Elements.txt"):
    """Loads the model chapter progression text."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"Error: The file {file_path} was not found. Please make sure it's in the same directory as app.py.")
        return None

# We might still want to extract images if we want to display them in Streamlit before/after analysis,
# or if we want to allow users to interact with them separately.
# For now, the core analysis will rely on Gemini's PDF capabilities.
def extract_images_for_display(pdf_file_bytes):
    """
    Extracts images from PDF bytes for display purposes.
    Returns a list of images (Pillow Image objects).
    """
    images = []
    try:
        doc = fitz.open(stream=pdf_file_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes_data = base_image["image"]
                image = Image.open(io.BytesIO(image_bytes_data))
                images.append({"page": page_num + 1, "image": image, "bbox": page.get_image_bbox(img)})
        doc.close()
    except Exception as e:
        st.warning(f"Could not extract images for display from PDF: {e}")
        return []
    return images


def analyze_with_llm(pdf_file_bytes, pdf_filename, model_progression_text, grade_level):
    """
    Analyzes the uploaded PDF chapter using Google Gemini API based on the model progression.
    """
    st.info("Preparing PDF...")

    try:
        # Save the uploaded PDF bytes to a temporary file, as the Gemini API
        # can take a file path or a file-like object for uploads.
        # Using a named temporary file can be more robust.
        temp_pdf_path = pathlib.Path(f"temp_{pdf_filename}")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_file_bytes)

        st.info(f"Uploading '{pdf_filename}' to EeeBee...")
        # Upload the PDF using the File API
        # It's good practice to use the File API for documents, especially if they might be large.
        # Files are stored for 48 hours.
        uploaded_file = genai.upload_file(path=temp_pdf_path, display_name=pdf_filename, mime_type="application/pdf")
        st.success(f"'{pdf_filename}' uploaded successfully to Gemini (URI: {uploaded_file.uri})")

    except Exception as e:
        st.error(f"Error uploading PDF to EeeBee: {e}")
        if 'temp_pdf_path' in locals() and temp_pdf_path.exists():
            temp_pdf_path.unlink() # Clean up temp file
        return "Error during PDF upload to EeeBee.", "Error"
    
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
    st.info(f"Sending request to EeeBee model for {grade_level}... This may take some time for larger documents.")
    try:
        # Use the uploaded file in the prompt
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=65536, # Explicitly set max output tokens
            temperature=0.7,  # Add some creativity to avoid direct copying
        )
        response = model.generate_content(
            [uploaded_file, prompt_content],
            generation_config=generation_config
        )

        # --- Debugging: Print finish reason and safety feedback ---
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
            st.write(f"Gemini Finish Reason: {finish_reason}")
            
            # Check for copyright detection (finish_reason 4)
            if finish_reason == 4:
                st.error("Gemini detected potential copyright concerns. Since this is your own content being used for educational purposes, we need to adjust our approach.")
                st.warning("Try one of these solutions: 1) Modify your PDF content to be less like published material, 2) Break the document into smaller chunks, or 3) Change specific terminology that might be triggering the copyright filter.")
                
                # Clean up resources
                try:
                    genai.delete_file(uploaded_file.name)
                    st.info(f"Temporary file '{uploaded_file.display_name}' deleted from Gemini.")
                except Exception as e_del:
                    st.warning(f"Could not delete temporary file '{uploaded_file.display_name}' from Gemini: {e_del}")
                
                if temp_pdf_path.exists():
                    temp_pdf_path.unlink()
                
                return "Error: The model detected copyright concerns. Since this is your own material, try modifying the content to be more distinct from published works.", "Copyright Error"
            
            if response.candidates[0].safety_ratings:
                st.write("Safety Ratings:")
                for rating in response.candidates[0].safety_ratings:
                    st.write(f"- Category: {rating.category}, Probability: {rating.probability}")
        if response.prompt_feedback:
            st.write(f"Gemini Prompt Feedback: {response.prompt_feedback}")
        # --- End Debugging ---

        # Check if we have valid text in the response
        if hasattr(response, 'text') and response.text:
            improved_text = response.text
        else:
            # If there's no text property but we have candidates with content
            if response.candidates and hasattr(response.candidates[0], 'content') and response.candidates[0].content:
                # Extract text from parts if available
                parts = response.candidates[0].content.parts
                if parts:
                    improved_text = ''.join([part.text for part in parts if hasattr(part, 'text')])
                else:
                    raise Exception("No content parts found in response")
            else:
                raise Exception("No valid text content found in response")
        
        # It's good practice to delete the file from Gemini storage if no longer needed,
        # though they auto-delete after 48 hours.
        try:
            genai.delete_file(uploaded_file.name)
            st.info(f"Temporary file '{uploaded_file.display_name}' deleted from Gemini.")
        except Exception as e_del:
            st.warning(f"Could not delete temporary file '{uploaded_file.display_name}' from Gemini: {e_del}")

        if temp_pdf_path.exists():
            temp_pdf_path.unlink() # Clean up local temp file

        return improved_text, "LLM analysis and rewrite complete using Gemini."
    except Exception as e:
        st.error(f"Error during Gemini API call: {e}")
        # Clean up uploaded file on Gemini if an error occurs during generation
        try:
            genai.delete_file(uploaded_file.name)
            st.warning(f"Cleaned up file '{uploaded_file.display_name}' from Gemini after error.")
        except Exception as e_del_err:
            st.warning(f"Could not delete file from Gemini after error: {e_del_err}")

        if temp_pdf_path.exists(): # Clean up local temp file
            temp_pdf_path.unlink()
        return f"Error: Could not complete Gemini analysis. {e}", "Error"


def create_word_document(improved_text_markdown):
    """Creates a Word document from the improved text (Markdown formatted)."""
    doc = Document()
    # This is a very basic Markdown to DOCX conversion.
    # For more complex Markdown, a library like 'markdown' and then 'html2text' or 'pypandoc' might be needed,
    # or more sophisticated parsing logic.
    
    # For now, let's handle headings and paragraphs simply.
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
        # Add more heading levels if needed
        elif line.startswith("- ") or line.startswith("* "):
            # Basic list item handling (doesn't handle nested lists well without more logic)
            # For proper list handling, python-docx requires paragraph styles or more direct list creation.
            # This will just add it as a paragraph with a dash.
            doc.add_paragraph(line, style='ListBullet') # May need to define 'ListBullet' style or use default
        else:
            # Simple bold/italic handling - this is very rudimentary
            # A proper Markdown parser would be better.
            # For now, just add as a paragraph. The LLM output format is key.
            doc.add_paragraph(line)
            
    # In the future, we would also add images back into the document here,
    # or at least placeholders for where the image prompts are.
    return doc

def analyze_with_chunked_approach(pdf_file_bytes, pdf_filename, model_progression_text, grade_level):
    """
    Analyzes the PDF in smaller chunks to avoid triggering copyright protection.
    This is a fallback method when the regular analysis fails due to copyright concerns.
    """
    st.info("Using chunked approach to analyze PDF...")
    
    try:
        # Save the uploaded PDF bytes to a temporary file, as the Gemini API
        # can take a file path or a file-like object for uploads.
        temp_pdf_path = pathlib.Path(f"temp_{pdf_filename}")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_file_bytes)
            
        # Upload the entire PDF file to Gemini
        st.info(f"Uploading '{pdf_filename}' to EeeBee for chunked analysis...")
        uploaded_file = genai.upload_file(path=temp_pdf_path, display_name=pdf_filename, mime_type="application/pdf")
        st.success(f"'{pdf_filename}' uploaded successfully to Gemini (URI: {uploaded_file.uri})")
        
        # Extract text from PDF for determining page chunks
        doc = fitz.open(stream=pdf_file_bytes, filetype="pdf")
        total_pages = len(doc)
        
        # Determine chunk size (pages per chunk)
        pages_per_chunk = 5  # Can be adjusted based on content density
        
        # Define page ranges for chunked analysis
        page_ranges = []
        for start_page in range(0, total_pages, pages_per_chunk):
            end_page = min(start_page + pages_per_chunk - 1, total_pages - 1)
            page_ranges.append({
                "start": start_page + 1,  # 1-indexed for human readability
                "end": end_page + 1,
                "range_text": f"Pages {start_page+1}-{end_page+1} of {total_pages}"
            })
        
        doc.close()
        
        # Process each chunk
        analysis_results = []
        
        for idx, page_range in enumerate(page_ranges):
            st.info(f"Analyzing chunk {idx+1}/{len(page_ranges)}: {page_range['range_text']}...")
            
            prompt_content = f"""You are an expert in educational content development for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: You are analyzing CHUNK {idx+1} of {len(page_ranges)} ({page_range['range_text']}) from a book chapter for **{grade_level} (CBSE)**.
This is just a PORTION of the full chapter - focus only on improving this section according to the model.

**FOCUS ONLY ON PAGES {page_range['start']} to {page_range['end']} of the PDF.**

The book chapter is intended to align with NCERT, NCF, and NEP 2020 guidelines for **{grade_level}**.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

**FINAL CHAPTER STRUCTURE:**
Note: The final integrated chapter will follow this structure (you're only working on a portion):
1. Current Concepts
2. Hook (with Image Prompt)
3. Learning Outcome
4. Real world connection
5. Previous class concept
6. History
7. Summary
8. Link and Learn based Question
9. Image based question
10. Exercise (with question types like MCQs, Fill in the Blanks, etc.)
11. Skill based Activity
12. Activity Time – STEM
13. Creativity – Art
14. Case Study – Level 1
15. Case Study – Level 2

**Target Audience:** {grade_level} (CBSE Syllabus)

**Important Instructions:**
* Rewrite and improve ONLY the content from pages {page_range['start']} to {page_range['end']}
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
Do not include analysis or explanations - just the rewritten content.
"""
            
            try:
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=32768,
                    temperature=0.7,
                )
                
                # Send the full PDF but instruct to focus on specific pages
                response = model.generate_content(
                    [uploaded_file, prompt_content],
                    generation_config=generation_config
                )
                
                # Check for copyright detection
                if response.candidates and response.candidates[0].finish_reason == 4:
                    st.warning(f"Copyright detection on chunk {idx+1}. Trying with text-only fallback...")
                    
                    # Extract just the text for this page range as fallback
                    chunk_text = ""
                    for page_num in range(page_range['start']-1, page_range['end']):
                        page = doc.load_page(page_num)
                        chunk_text += page.get_text()
                    
                    # Modify prompt to indicate images won't be available
                    text_only_prompt = prompt_content + f"""

**NOTE: This is now processing text-only due to copyright concerns with the full PDF.**

**Text from these pages:**
'''
{chunk_text}
'''

Please rewrite and improve this content, noting that any image references will need to be based on the text descriptions only.
"""
                    
                    # Try again with text-only
                    response = model.generate_content(
                        [text_only_prompt],
                        generation_config=generation_config
                    )
                
                if hasattr(response, 'text') and response.text:
                    improved_chunk = response.text
                    analysis_results.append(improved_chunk)
                else:
                    # Handle alternative response format if needed
                    if response.candidates and hasattr(response.candidates[0], 'content') and response.candidates[0].content:
                        parts = response.candidates[0].content.parts
                        if parts:
                            improved_chunk = ''.join([part.text for part in parts if hasattr(part, 'text')])
                            analysis_results.append(improved_chunk)
                        else:
                            analysis_results.append(f"[Error processing chunk {idx+1}]")
                    else:
                        analysis_results.append(f"[Error processing chunk {idx+1}]")
                        
            except Exception as chunk_e:
                st.warning(f"Error processing chunk {idx+1}: {chunk_e}")
                analysis_results.append(f"[Error processing chunk {idx+1}: {chunk_e}]")
        
        # Combine results
        combined_result = "\n\n".join(analysis_results)
        
        # Add final integration prompt to ensure coherence
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

**Important:**
* Ensure smooth transitions between chunks
* Remove any redundancies or repeated information
* Create a consistent style and tone throughout
* Add a chapter introduction and conclusion if they don't exist
* Format as a proper textbook chapter with appropriate headings and subheadings
* Ensure all Bloom's Taxonomy questions are integrated appropriately
* STRICTLY follow the REQUIRED CONTENT STRUCTURE above
* Maintain all image prompts and image references from the chunks

**Content to integrate:**
{combined_result}

Provide the complete, integrated chapter in Markdown format.
"""
        
        try:
            integration_config = genai.types.GenerationConfig(
                max_output_tokens=65536,
                temperature=0.4,  # Lower temperature for more coherent integration
            )
            
            final_response = model.generate_content(
                [integration_prompt],
                generation_config=integration_config
            )
            
            if hasattr(final_response, 'text') and final_response.text:
                final_improved_text = final_response.text
            else:
                # Handle alternative response format
                if final_response.candidates and hasattr(final_response.candidates[0], 'content') and final_response.candidates[0].content:
                    parts = final_response.candidates[0].content.parts
                    if parts:
                        final_improved_text = ''.join([part.text for part in parts if hasattr(part, 'text')])
                    else:
                        raise Exception("No content parts found in final integration response")
                else:
                    raise Exception("No valid text content found in final integration response")
            
            # Clean up resources
            try:
                genai.delete_file(uploaded_file.name)
                st.info(f"Temporary file '{uploaded_file.display_name}' deleted from Gemini.")
            except Exception as e_del:
                st.warning(f"Could not delete temporary file '{uploaded_file.display_name}' from Gemini: {e_del}")
            
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()
                    
            return final_improved_text, "LLM analysis and rewrite complete using chunked approach with full PDF access."
            
        except Exception as integration_e:
            st.error(f"Error during final integration: {integration_e}")
            
            # Clean up resources
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
            
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()
                
            # Return the combined chunks without final integration
            return combined_result, "Partial analysis complete - final integration failed."
            
    except Exception as e:
        st.error(f"Error during chunked PDF analysis: {e}")
        
        # Clean up resources
        if 'uploaded_file' in locals():
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
        
        if 'temp_pdf_path' in locals() and temp_pdf_path.exists():
            temp_pdf_path.unlink()
            
        return f"Error: Could not complete chunked analysis. {e}", "Error"

# --- Helper Functions for Content Generation ---

def create_specific_prompt(content_type, grade_level, model_progression_text, subject_type="General"):
    """Creates a prompt focused on a specific content type"""
    
    if subject_type == "Mathematics":
        # Math-specific prompts that combine Model Chapter Progression with math-specific elements
        base_prompt = f"""You are an expert in mathematical education content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes.

You are analyzing a mathematics book chapter intended for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines for Mathematics education.

**Model Chapter Progression and Elements (Base Structure):**
---
{model_progression_text}
---

**Target Audience:** {grade_level} (CBSE Mathematics Syllabus)
"""
        
        if content_type == "chapter":
            prompt = base_prompt + f"""
Your task is to generate COMPREHENSIVE MATHEMATICS CHAPTER CONTENT following the Model Chapter Progression structure enhanced with mathematics-specific elements.

**REQUIRED SECTIONS (Generate ALL with substantial content, combining Model Chapter Progression with Math-specific elements):**

## I. Chapter Opener (Following Model Chapter Progression + Math Enhancement)

1. **Chapter Title** - Engaging and mathematically focused
2. **Hook (with Image Prompt)** (100-150 words)
   - Create an engaging mathematical opening that captures student interest
   - Use real-life mathematical scenarios, surprising mathematical facts, or thought-provoking mathematical questions
   - Connect to students' daily mathematical experiences
   - Include a detailed image prompt for a compelling mathematical visual
   - Follow the "Big Question or real-life problem" approach from Model Chapter Progression

3. **Real-World Connection** (300-400 words)
   - Provide multiple real-world applications of the mathematical concepts
   - Show how math is used in everyday life situations
   - Include examples from technology, engineering, finance, science, etc.
   - Link to students' lives and current events as per Model Chapter Progression
   - Connect to mathematical careers and future studies

4. **Learning Outcomes + Previous Class Link** (200-300 words)
   - List specific, measurable mathematical learning objectives
   - Use action verbs (define, explain, calculate, apply, analyze, solve, prove, etc.)
   - Align with Bloom's Taxonomy levels for mathematics
   - Connect to CBSE mathematics curriculum standards
   - Link to prior mathematical knowledge from previous classes
   - Make outcomes student-centered and action-oriented

5. **Chapter Map/Overview** (150-200 words)
   - Visual layout of mathematical concepts (mind map or flowchart description)
   - Show mathematical progressions and connections
   - Include brief explanations of how concepts build upon each other

6. **Meet the Character (EeeBee)** (100-150 words)
   - Introduce EeeBee as a mathematical guide/helper throughout the chapter
   - Show how EeeBee will assist with mathematical problem-solving and exploration

## II. Core Content Sections (Enhanced with Math-Specific Elements)

7. **Introduction of Chapter** (200-300 words)
   - Give a related chapter introduction that sets the mathematical context
   - Explain the importance of the mathematical concepts to be learned
   - Connect to the broader mathematical curriculum
   - Motivate students about the mathematical journey ahead
   - Activate prior mathematical knowledge with questions or scenarios

8. **History of Chapter** (300-400 words)
   - Provide comprehensive historical background of the mathematical concepts
   - Include key mathematicians, their contributions, and discoveries
   - Explain the timeline of mathematical developments
   - Connect historical context to modern mathematical understanding
   - Show how mathematical concepts evolved over time
   - Integrate directly into explanation as per Model Chapter Progression

9. **Warm-up Questions** (200-250 words)
   - Create 5-7 engaging warm-up questions that:
     * Connect to prior mathematical knowledge
     * Introduce the topic informally through real-life mathematical scenarios
     * Spark mathematical curiosity and set the tone
     * Engage students right at the beginning
   - Include a mix of question types (mental math, real-world problems, pattern recognition)

10. **Current Concepts** (2500-3000 words minimum)
    For each major concept in the chapter, include ALL of the following:
    
    **A. Concept Introduction** (200-300 words per concept)
    - Clear introduction to each mathematical concept
    - Simple, clear mathematical language
    - Use analogies and mathematical examples
    - Explain the mathematical significance and applications
    
    **B. Mathematical Explanation** (400-500 words per concept)
    - Multi-modal content (text + visual descriptions)
    - Provide 5 different worked examples for each concept
    - Include step-by-step solutions with clear explanations
    - Use varied difficulty levels and question formats
    - Show different mathematical approaches where applicable
    
    **C. Visuals** (Throughout each concept)
    - Include detailed image prompts for mathematical diagrams, graphs, and illustrations
    - Labeled, relevant mathematical diagrams and infographics
    - Visual descriptions for every mathematical concept
    
    **D. Mathematical Activities/Experiments** (200-250 words per concept)
    - Step-by-step mathematical experiments or investigations
    - Inquiry-based mathematical activities
    - Real-life mathematical connections
    - Use mathematical tools, software, or physical materials
    
    **E. Check Your Understanding** (150-200 words per concept)
    - Short MCQs and short answers after each mathematical concept
    - Immediate feedback or answer explanations
    - Questions at various Bloom's Taxonomy levels
    
    **F. Key Mathematical Terms** (100-150 words per concept)
    - Highlighted mathematical terminology in text
    - Clear mathematical definitions
    - Include mathematical properties, formulas, and theorems
    
    **G. Mathematical Applications** (200-250 words per concept)
    - Show relevance to daily life, mathematical careers, technology
    - Connect to other mathematical concepts and subjects
    - Include mathematical innovations and discoveries
    
    **H. Fun Mathematical Facts** (100-150 words per concept)
    - Include interesting mathematical facts related to the concept
    - Share surprising mathematical discoveries or applications
    - Connect to mathematical history or modern developments
    
    **I. Think About It! (Mathematical Exploration)** (100-150 words per concept)
    - Present thought-provoking mathematical questions or scenarios
    - Include surprising mathematical connections or patterns
    - Encourage mathematical thinking and exploration
    
    **J. Mental Mathematics** (150-200 words per concept)
    - Provide mental mathematics strategies and techniques
    - Include quick calculation methods and shortcuts
    - Create practice problems for mental math skills

## III. Special Features (Integrated Across Chapter - Following Model Chapter Progression)

11. **Common Mathematical Misconceptions** (200-300 words)
    - 2-3 misconceptions per mathematical concept
    - Correct early mathematical misunderstandings
    - Provide clear explanations of correct mathematical thinking

12. **21st Century Skills Focus** (300-400 words)
    - **Mathematical Design Challenge** (Creativity in problem-solving)
    - **Mathematical Debate** (Communication & Critical Thinking about mathematical concepts)
    - **Collaborate & Create** (Teamwork in mathematical projects)

13. **Differentiation** (200-300 words)
    - Challenge sections for advanced mathematical learners
    - Support sections for mathematical revision/simplified tasks
    - Multiple approaches to mathematical problem-solving

14. **Technology Integration** (150-200 words)
    - Mathematical software and tools
    - Student tech-based mathematical exploration ideas
    - Digital mathematical simulations and visualizations

15. **Character Integration** (Throughout)
    - EeeBee appears throughout to ask mathematical questions
    - Give mathematical hints and share fun mathematical facts
    - Provide mathematical recaps and connections

## IV. Chapter Wrap-Up (Following Model Chapter Progression)

16. **Self-Assessment Checklist** (200-250 words)
    - Create a comprehensive self-assessment checklist for the whole mathematical chapter
    - Use bullet points for easy checking
    - Include mathematical skills, concepts, and applications
    - Help students evaluate their own mathematical understanding

17. **Mathematical Summary** (300-400 words)
    - Bullet-point or infographic summary of mathematical concepts
    - Include key mathematical formulas and important facts
    - Organize by individual mathematical concepts covered

18. **Chapter-wise Miscellaneous Exercise** (500-600 words)
    Create a comprehensive mix of mathematical question types:
    - **MCQs** (5 questions with detailed solutions)
    - **Short/Long Answer** (3 short, 2 long mathematical problems)
    - **Open-ended Mathematical Problems** (2 questions)
    - **Assertion & Reason** (3 mathematical statements with reasoning)
    - **Mathematical Concept Mapping** (1 comprehensive map)
    - **True/False with Mathematical Justification** (5 statements)
    - **Mathematical Case Studies** (1 real-world mathematical scenario)
    - **Mathematical Puzzle** (1 engaging mathematical puzzle)
    - **Thinking Based Mathematical Activities** including:
      * Mathematical Crossword Puzzle
      * Mathematical Sudoku or number puzzle
      * Mathematical Project ideas
      * Research and Presentation topics on mathematical concepts

19. **Apply Your Mathematical Knowledge** (200-300 words)
    - Real-world mathematical application tasks
    - Project-based mathematical problems encouraging synthesis and creativity
    - Mathematical investigations and explorations

**CONTENT REQUIREMENTS:**
* **Minimum Total Length**: 8000-10000 words for the complete mathematics chapter content
* **Mathematical Accuracy**: Ensure all mathematical content is accurate and age-appropriate
* **Clear Mathematical Language**: Use precise mathematical terminology suitable for {grade_level}
* **Step-by-step Solutions**: Provide detailed mathematical working for all examples
* **Visual Integration**: Include detailed image prompts for mathematical diagrams, graphs, and illustrations
* **Progressive Difficulty**: Structure content from basic to advanced mathematical concepts
* **Model Chapter Progression Compliance**: Follow the structure and principles from the Model Chapter Progression

**FORMATTING REQUIREMENTS:**
* Use Markdown formatting with clear headings (# ## ###)
* Include mathematical expressions using appropriate notation
* Use **bold** for key mathematical terms and *italics* for emphasis
* Create well-structured mathematical explanations
* Include image prompts marked as: [PROMPT FOR NEW IMAGE: detailed mathematical diagram description]
* Follow the visual variety and layout principles from Model Chapter Progression

**QUALITY STANDARDS:**
* Each section should be mathematically rigorous and comprehensive
* Ensure mathematical concepts flow logically from one to the next
* Include multiple mathematical approaches and problem-solving strategies
* Maintain consistency in mathematical notation and terminology
* Integrate EeeBee character throughout for engagement
* Balance theoretical mathematical understanding with practical applications

Analyze the PDF document thoroughly and create improved mathematical content that expands significantly on what's provided while maintaining all original mathematical concepts and terminology.

Provide ONLY the comprehensive mathematics chapter content in Markdown format.
"""
        
        elif content_type == "exercises":
            prompt = base_prompt + f"""
Your task is to generate COMPREHENSIVE MATHEMATICS EXERCISES based on the chapter content in the PDF, following the Model Chapter Progression principles for review and assessment.

**Following Model Chapter Progression Review Structure:**
Create a comprehensive mix of mathematical question types that align with the Model Chapter Progression's approach to review questions:

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

**Special Mathematical Features (Following Model Chapter Progression):**
- **EeeBee Integration**: Include questions where EeeBee guides mathematical thinking
- **Technology Integration**: Questions involving mathematical software, calculators, or digital tools
- **Differentiation**: Include challenge problems for advanced learners and support questions for revision
- **21st Century Skills**: Collaborative mathematical problems and communication-based questions

Ensure that:
* Questions cover ALL important mathematical concepts from the PDF
* Questions follow Bloom's Taxonomy at various levels (Remember, Understand, Apply, Analyze, Evaluate, Create)
* Mathematical language is clear and appropriate for {grade_level}
* Questions increase in difficulty from basic recall to higher-order mathematical thinking
* All exercises include detailed mathematical solutions with step-by-step working
* Content is formatted in Markdown with proper mathematical notation
* Include EeeBee character integration throughout exercises
* Follow Model Chapter Progression principles for comprehensive assessment

Provide ONLY the comprehensive mathematical exercises in Markdown format.
"""
        
        elif content_type == "skills":
            prompt = base_prompt + f"""
Your task is to generate MATHEMATICAL SKILL-BASED ACTIVITIES and STEM projects based on the chapter content in the PDF, following the Model Chapter Progression approach to hands-on learning and real-world applications.

**Following Model Chapter Progression Activity Structure:**

## Mathematical Skill-Based Activities (Hands-on Mathematical Learning)

Create at least 3 comprehensive mathematical activities that follow the Model Chapter Progression principles:

**Activity Structure for Each:**
1. **Clear Mathematical Objective** - Specific learning goals aligned with chapter concepts
2. **Materials Required** - Mathematical tools, manipulatives, technology, or everyday items
3. **Step-by-Step Mathematical Procedure** - Detailed instructions with mathematical reasoning
4. **Inquiry-Based Mathematical Exploration** - Questions that guide mathematical discovery
5. **Real-Life Mathematical Connections** - How the activity relates to daily mathematical applications
6. **EeeBee Integration** - How EeeBee guides or assists in the mathematical activity
7. **Mathematical Reflection Questions** - Encourage deeper mathematical thinking
8. **Expected Mathematical Outcomes** - What students should learn or discover

**Types of Mathematical Activities:**
- **Mathematical Experiments/Investigations** - Hands-on exploration of mathematical concepts
- **Mathematical Manipulative Activities** - Using physical or digital tools to understand concepts
- **Mathematical Problem-Solving Challenges** - Real-world mathematical scenarios
- **Mathematical Pattern Recognition Activities** - Discovering mathematical relationships
- **Mathematical Measurement and Data Collection** - Practical mathematical applications

## Mathematical STEM Projects (Integration Focus)

Create at least 2 comprehensive projects that integrate mathematics with Science, Technology, and Engineering:

**Project Structure for Each:**
1. **Mathematical Integration Focus** - How math connects with other STEM fields
2. **Real-World Mathematical Application** - Authentic mathematical problem-solving scenarios
3. **Technology Integration** - Mathematical software, apps, or digital tools
4. **Collaborative Mathematical Work** - Teamwork and mathematical communication
5. **Mathematical Design Challenge** - Creative problem-solving with mathematical constraints
6. **Mathematical Analysis and Calculations** - Detailed mathematical work required
7. **Mathematical Presentation Component** - Sharing mathematical findings and reasoning
8. **Assessment Criteria** - How mathematical understanding will be evaluated

**STEM Integration Examples:**
- **Mathematical Modeling in Science** - Using math to understand scientific phenomena
- **Engineering Design with Mathematical Constraints** - Applying mathematical principles to design
- **Technology-Enhanced Mathematical Problem Solving** - Using digital tools for mathematical exploration
- **Mathematical Data Analysis Projects** - Real-world data collection and mathematical interpretation

## Special Features (Following Model Chapter Progression)

**21st Century Mathematical Skills Development:**
- **Mathematical Communication** - Explaining mathematical reasoning clearly
- **Mathematical Collaboration** - Working together on mathematical problems
- **Mathematical Critical Thinking** - Analyzing and evaluating mathematical solutions
- **Mathematical Creativity** - Finding innovative approaches to mathematical problems

**Differentiation in Mathematical Activities:**
- **Challenge Extensions** - Advanced mathematical explorations for gifted learners
- **Support Modifications** - Simplified mathematical approaches for struggling learners
- **Multiple Mathematical Approaches** - Different ways to engage with the same mathematical concepts

**Technology Integration:**
- **Mathematical Software and Apps** - Specific tools for mathematical exploration
- **Digital Mathematical Simulations** - Virtual mathematical experiments
- **Mathematical Visualization Tools** - Software for creating mathematical diagrams and models

**Character Integration:**
- **EeeBee's Mathematical Challenges** - Special problems or investigations led by EeeBee
- **EeeBee's Mathematical Tips** - Helpful hints and strategies for mathematical success
- **EeeBee's Mathematical Discoveries** - Fun mathematical facts and connections

**Differentiation in Creative Mathematical Projects:**
- **Multiple Artistic Approaches** - Different ways to express the same mathematical concepts
- **Varied Complexity Levels** - Projects suitable for different mathematical skill levels
- **Choice in Creative Expression** - Students select their preferred artistic medium for mathematical exploration

**Assessment and Reflection:**
- **Mathematical Understanding Criteria** - How mathematical learning is demonstrated through art
- **Creative Expression Evaluation** - Assessing artistic quality and mathematical integration
- **Mathematical Communication Assessment** - Evaluating explanation of mathematical-artistic connections
- **Peer Mathematical-Artistic Appreciation** - Students analyzing and appreciating each other's mathematical art

**Content Requirements:**
* Projects connect mathematical concepts to various art forms appropriately for {grade_level}
* Allow for creative expression while reinforcing mathematical learning
* Can be completed with commonly available art supplies and mathematical tools
* Include clear mathematical learning objectives and artistic goals
* Encourage mathematical problem-solving through creative expression
* Connect to real-world mathematical applications and careers

**Quality Standards:**
* Ensure mathematical accuracy within artistic expression
* Balance creative freedom with mathematical learning objectives
* Include multiple approaches to mathematical-artistic integration
* Maintain consistency in mathematical notation and terminology
* Integrate seamlessly with chapter mathematical content
* Respect diverse artistic abilities while maintaining mathematical rigor

Format the content in Markdown with proper mathematical notation and organization.

Provide ONLY the Mathematical Skill Activities and STEM Projects in Markdown format.
"""
        
        elif content_type == "art":
            prompt = base_prompt + f"""
Your task is to generate MATHEMATICS-INTEGRATED CREATIVE LEARNING projects based on the chapter content in the PDF, following the Model Chapter Progression approach to creative expression and art integration.

**Following Model Chapter Progression Creative Integration Structure:**

## Mathematical Art Projects (Creative Mathematical Expression)

Create at least 3 creative projects that connect mathematical concepts to various art forms, following Model Chapter Progression principles:

**Project Structure for Each:**
1. **Mathematical Learning Objective** - Clear mathematical goals through artistic expression
2. **Art Form Integration** - Visual arts, music, drama, digital art, or multimedia
3. **Mathematical Concepts Highlighted** - Specific mathematical ideas explored through art
4. **Materials and Tools** - Art supplies, mathematical tools, technology needed
5. **Step-by-Step Mathematical-Artistic Process** - Detailed creative procedure with mathematical reasoning
6. **EeeBee's Creative Guidance** - How EeeBee inspires and guides the artistic mathematical exploration
7. **Mathematical Reflection and Analysis** - Questions connecting art creation to mathematical understanding
8. **Showcase and Communication** - How students share their mathematical-artistic creations

**Types of Mathematical Art Integration:**
- **Geometric Art and Patterns** - Using mathematical shapes, symmetry, and patterns in visual art
- **Mathematical Music and Rhythm** - Exploring mathematical relationships in musical composition
- **Mathematical Drama and Storytelling** - Acting out mathematical concepts and problem-solving scenarios
- **Mathematical Digital Art** - Using technology to create mathematical visualizations and designs
- **Mathematical Sculpture and 3D Models** - Building mathematical concepts through physical construction

## Mathematical Case Studies (Real-World Mathematical Scenarios)

**Case Study – Level 1 (Accessible Mathematical Analysis):**
Create at least 1 simpler case study that:
- Presents a real-world mathematical scenario appropriate for {grade_level}
- Includes guided mathematical analysis questions
- Is accessible to all students with basic mathematical skills
- Connects to students' daily mathematical experiences
- Follows Model Chapter Progression principles of real-world connection

**Case Study – Level 2 (Advanced Mathematical Challenge):**
Create at least 1 more complex case study that:
- Challenges students with multi-step mathematical problems
- Requires deeper application of mathematical concepts from the chapter
- Encourages higher-order mathematical thinking skills
- Integrates multiple mathematical concepts and problem-solving strategies
- Follows Model Chapter Progression principles of differentiated challenge

**Case Study Structure for Each:**
1. **Real-World Mathematical Context** - Authentic scenario requiring mathematical analysis
2. **Mathematical Background Information** - Relevant data, facts, and mathematical context
3. **Guided Mathematical Questions** - Progressive questions leading to deeper understanding
4. **Mathematical Analysis Requirements** - Specific mathematical skills and concepts to apply
5. **Creative Mathematical Solutions** - Encouraging innovative mathematical approaches
6. **Mathematical Communication Component** - Presenting mathematical findings clearly
7. **EeeBee's Mathematical Insights** - Character guidance and mathematical connections
8. **Extension Mathematical Challenges** - Additional mathematical explorations for interested students

## Special Creative Features (Following Model Chapter Progression)

**21st Century Mathematical-Creative Skills:**
- **Mathematical Design Thinking** - Creative problem-solving with mathematical constraints
- **Mathematical Communication through Art** - Expressing mathematical ideas creatively
- **Mathematical Collaboration in Creative Projects** - Teamwork in mathematical-artistic endeavors
- **Mathematical Innovation and Creativity** - Finding new ways to represent mathematical concepts

**Technology Integration in Mathematical Art:**
- **Mathematical Design Software** - Programs for creating mathematical art and visualizations
- **Digital Mathematical Storytelling** - Using technology to tell mathematical stories
- **Mathematical Animation and Simulation** - Creating moving mathematical representations
- **Mathematical Virtual Reality** - Immersive mathematical experiences

**Character Integration in Creative Projects:**
- **EeeBee's Art Gallery** - Showcasing mathematical art inspired by EeeBee
- **EeeBee's Mathematical Stories** - Creative narratives featuring mathematical adventures
- **EeeBee's Design Challenges** - Creative mathematical problems posed by the character

**Differentiation in Creative Mathematical Projects:**
- **Multiple Artistic Approaches** - Different ways to express the same mathematical concepts
- **Varied Complexity Levels** - Projects suitable for different mathematical skill levels
- **Choice in Creative Expression** - Students select their preferred artistic medium for mathematical exploration

**Assessment and Reflection:**
- **Mathematical Understanding Criteria** - How mathematical learning is demonstrated through art
- **Creative Expression Evaluation** - Assessing artistic quality and mathematical integration
- **Mathematical Communication Assessment** - Evaluating explanation of mathematical-artistic connections
- **Peer Mathematical-Artistic Appreciation** - Students analyzing and appreciating each other's mathematical art

**Content Requirements:**
* Projects connect mathematical concepts to various art forms appropriately for {grade_level}
* Allow for creative expression while reinforcing mathematical learning
* Can be completed with commonly available art supplies and mathematical tools
* Include clear mathematical learning objectives and artistic goals
* Encourage mathematical problem-solving through creative expression
* Connect to real-world mathematical applications and careers

**Quality Standards:**
* Ensure mathematical accuracy within artistic expression
* Balance creative freedom with mathematical learning objectives
* Include multiple approaches to mathematical-artistic integration
* Maintain consistency in mathematical notation and terminology
* Integrate seamlessly with chapter mathematical content
* Respect diverse artistic abilities while maintaining mathematical rigor

Format the content in Markdown with proper mathematical notation and organization.

Provide ONLY the Mathematics-Integrated Creative Learning content in Markdown format.
"""
    
    else:
        # Original general subject prompts (existing code)
        base_prompt = f"""You are an expert in educational content development, specifically for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: This is the user's own copyright material, and they have explicitly authorized its analysis and transformation for educational purposes.

You are analyzing a book chapter intended for **{grade_level} (CBSE)**.
The book is intended to align with NCERT, NCF, and NEP 2020 guidelines.

**Model Chapter Progression and Elements:**
---
{model_progression_text}
---

**Target Audience:** {grade_level} (CBSE Syllabus)
"""
    
    if content_type == "chapter":
        prompt = base_prompt + f"""
Your task is to generate COMPREHENSIVE CORE CHAPTER CONTENT that should be equivalent to a complete textbook chapter.

**REQUIRED SECTIONS (Generate ALL with substantial content):**

1. **Current Concepts** (1000-1200 words minimum)
   - Provide detailed explanations of ALL key concepts from the PDF
   - Include multiple examples for each concept
   - Use analogies and real-world connections to explain complex ideas
   - Break down concepts into sub-concepts with clear explanations
   - Include scientific principles, formulas, or definitions where applicable
   - Give questions for each current concept - 3 MCQs, 2 Short questions, 1 Long question
   - Give activity according to the concept
   - Give fun fact for each concept
   - Give key points for each concept
   - Give common misconceptions for each concept
   - Mark concepts which are exactly coming from the PDF and give some extra concepts for higher level understanding (like how a foundation book has them)
   - Make sure there is no repetition of concepts (even by just changing some words)

2. **Hook (with Image Prompt)** (50-70 words)
   - Create an engaging opening that captures student interest
   - Use storytelling, surprising facts, or thought-provoking questions
   - Connect to students' daily experiences or current events
   - Include a detailed image prompt for a compelling visual

3. **Learning Outcome** (50-70 words)
   - List specific, measurable learning objectives
   - Use action verbs (analyze, evaluate, create, etc.)
   - Align with Bloom's Taxonomy levels
   - Connect to CBSE curriculum standards

4. **Real World Connection** (35-50 words)
   - Provide multiple real-world applications of the concepts
   - Include current examples from technology, environment, health, etc.
   - Explain how the concepts impact daily life
   - Connect to career opportunities and future studies

5. **Previous Class Concept** (50-100 words)
   - Give the concept name and the previous class it was studied in according to NCERT textbooks.

6. **History** (70-100 words)
   - Provide comprehensive historical background
   - Include key scientists, inventors, or historical figures
   - Explain the timeline of discoveries or developments
   - Connect historical context to modern understanding

7. **Summary** (600-800 words)
   - Create detailed concept-wise summaries (not just one overall summary)
   - Include key points, formulas, and important facts
   - Organize by individual concepts covered in the chapter
   - Provide clear, concise explanations that reinforce learning

8. **Link and Learn Based Question** (200-300 words)
   - Create 3-5 questions that connect different concepts
   - Include questions that link to other subjects or real-world scenarios
   - Provide detailed explanations for the connections

9. **Image Based Question** (200-300 words)
   - Create 3-5 questions based on images/diagrams from the chapter
   - Include detailed image descriptions if creating new image prompts
   - Ensure questions test understanding, not just observation

**CONTENT REQUIREMENTS:**
* **Minimum Total Length**: 6000-7000 words for the complete chapter content
* **Detailed Explanations**: Each concept should be explained thoroughly with multiple paragraphs
* **Examples and Illustrations**: Include numerous examples, case studies, and practical applications
* **Age-Appropriate Language**: Use vocabulary suitable for {grade_level} but don't oversimplify
* **Engaging Tone**: Write in an engaging, conversational style that maintains student interest
* **Clear Structure**: Use proper headings, subheadings, and formatting
* **Visual Integration**: Include detailed image prompts throughout the content

**FORMATTING REQUIREMENTS:**
* Use Markdown formatting with clear headings (# ## ###)
* Include bullet points and numbered lists where appropriate
* Use **bold** for key terms and *italics* for emphasis
* Create well-structured paragraphs (3-5 sentences each)
* Include image prompts marked as: [PROMPT FOR NEW IMAGE: detailed description]

**QUALITY STANDARDS:**
* Each section should be substantial and comprehensive
* Avoid superficial coverage - go deep into each topic
* Include multiple perspectives and approaches to concepts
* Ensure content flows logically from one section to the next
* Maintain consistency in terminology and explanations

**IMPORTANT**: This should read like a complete, professional textbook chapter that a teacher could use directly in class. Do NOT provide brief or summary-style content. Each section should be fully developed with rich, detailed explanations.

Analyze the PDF document thoroughly and create improved content that expands significantly on what's provided while maintaining all original concept names and terminology.

Provide ONLY the comprehensive chapter content in Markdown format. Do not include exercises, activities, or art projects.
"""
    
    elif content_type == "exercises":
        prompt = base_prompt + f"""
Your task is to generate COMPREHENSIVE EXERCISES based on the chapter content in the PDF.

Create the following exercise types:
1. MCQ (Multiple Choice Questions) - at least 10 questions
2. Assertion and Reason - at least 5 questions
3. Fill in the Blanks - at least 10 questions
4. True False - at least 10 statements
5. Define the following terms - at least 10 terms
6. Match the column - at least 2 sets with 5 matches each
7. Give Reason for the following Statement (Easy Level) - at least 5 questions
8. Answer in Brief (Moderate Level) - at least 5 questions
9. Answer in Detail (Hard Level) - at least 5 questions

Ensure that:
* Questions cover ALL important concepts from the PDF
* Questions follow Bloom's Taxonomy at various levels (Remember, Understand, Apply, Analyze, Evaluate, Create)
* Language is clear and appropriate for {grade_level}
* Questions increase in difficulty from basic recall to higher-order thinking
* All exercises include correct answers or model solutions
* The content is formatted in Markdown with proper headings and organization

Do NOT directly copy questions from the PDF. Create new, original questions based on the content.

Provide ONLY the exercises in Markdown format.
"""
    
    elif content_type == "skills":
        prompt = base_prompt + f"""
Your task is to generate SKILL-BASED ACTIVITIES and STEM projects based on the chapter content in the PDF.

Create the following:
1. Skill-based Activities - At least 3 hands-on activities that:
   * Reinforce the key concepts from the chapter
   * Develop practical skills relevant to the subject
   * Can be completed with easily available materials
   * Include clear step-by-step instructions

2. Activity Time – STEM Projects - At least 2 projects that:
   * Integrate Science, Technology, Engineering and Mathematics
   * Connect to real-world applications of the chapter concepts
   * Encourage problem-solving and critical thinking
   * Include materials needed, procedure, and expected outcomes

For each activity/project, include:
* A clear title and objective
* Materials required
* Detailed procedure with steps
* Safety precautions where applicable
* Questions for reflection
* Expected outcomes or learning points

Format the content in Markdown with proper headings, lists, and organization.

Provide ONLY the Skill Activities and STEM Projects in Markdown format.
"""
    
    elif content_type == "art":
        prompt = base_prompt + f"""
Your task is to generate ART-INTEGRATED LEARNING projects based on the chapter content in the PDF.

Create the following:
1. Creativity – Art Projects - At least 3 creative projects that:
   * Connect the chapter concepts to various art forms (visual arts, music, drama, etc.)
   * Allow for creative expression while reinforcing learning
   * Can be completed with commonly available art supplies
   * Are age-appropriate for {grade_level} students

2. Case Study – Level 1 - At least 1 simpler case study that:
   * Presents a real-world scenario related to the chapter concepts
   * Includes guiding questions for analysis
   * Is accessible to all students

3. Case Study – Level 2 - At least 1 more complex case study that:
   * Challenges students with a multi-faceted scenario
   * Requires deeper application of chapter concepts
   * Encourages higher-order thinking skills

For each project/case study, include:
* A clear title and learning objective
* Materials needed (for art projects)
* Detailed instructions or scenario description
* Guiding questions or reflection points
* Assessment criteria or expected outcomes

Format the content in Markdown with proper headings, lists, and organization.

Provide ONLY the Art-Integrated Learning content in Markdown format.
"""
    
    return prompt

def generate_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text, subject_type="General", use_chunked=False):
    """Generates specific content based on content type"""
    prompt = create_specific_prompt(content_type, grade_level, model_progression_text, subject_type)
    
    if not use_chunked:
        # Standard approach
        temp_pdf_path = pathlib.Path(f"temp_{pdf_filename}")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)
        
        try:
            # Upload the PDF
            st.info(f"Uploading '{pdf_filename}' to EeeBee...")
            uploaded_file = genai.upload_file(path=temp_pdf_path, display_name=pdf_filename, mime_type="application/pdf")
            st.success(f"'{pdf_filename}' uploaded successfully to Gemini")
            
            # Generate content
            st.info(f"Generating {content_type} content for {grade_level}...")
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=65536,
                temperature=0.7,
            )
            
            response = model.generate_content(
                [uploaded_file, prompt],
                generation_config=generation_config
            )
            
            # Check for copyright detection
            if response.candidates and response.candidates[0].finish_reason == 4:
                st.error("Gemini detected potential copyright concerns. Trying chunked approach...")
                # Clean up resources
                genai.delete_file(uploaded_file.name)
                temp_pdf_path.unlink()
                # Use chunked approach instead
                return generate_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text, subject_type, use_chunked=True)
            
            # Extract text from response
            if hasattr(response, 'text') and response.text:
                result_text = response.text
            else:
                # Handle alternative response format
                if response.candidates and hasattr(response.candidates[0], 'content') and response.candidates[0].content:
                    parts = response.candidates[0].content.parts
                    if parts:
                        result_text = ''.join([part.text for part in parts if hasattr(part, 'text')])
                    else:
                        raise Exception("No content parts found in response")
                else:
                    raise Exception("No valid text content found in response")
            
            # Clean up resources
            genai.delete_file(uploaded_file.name)
            temp_pdf_path.unlink()
            
            return result_text, "Generated successfully using standard approach."
            
        except Exception as e:
            st.error(f"Error during Gemini API call: {e}")
            # Clean up resources
            if 'uploaded_file' in locals():
                try:
                    genai.delete_file(uploaded_file.name)
                except:
                    pass
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()
            return None, f"Error: {str(e)}"
    else:
        # Chunked approach
        return analyze_with_chunked_approach_for_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text, subject_type)

def analyze_with_chunked_approach_for_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text, subject_type):
    """Specialized chunked approach for specific content types"""
    st.info(f"Using chunked approach to generate {content_type} content...")
    
    try:
        # Save the uploaded PDF bytes to a temporary file
        temp_pdf_path = pathlib.Path(f"temp_{pdf_filename}")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)
            
        # Upload the entire PDF file to Gemini
        st.info(f"Uploading '{pdf_filename}' to EeeBee for chunked analysis...")
        uploaded_file = genai.upload_file(path=temp_pdf_path, display_name=pdf_filename, mime_type="application/pdf")
        st.success(f"'{pdf_filename}' uploaded successfully to Gemini")
        
        # Extract text from PDF for determining page chunks
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        # Determine chunk size (pages per chunk)
        pages_per_chunk = 5  # Can be adjusted based on content density
        
        # Define page ranges for chunked analysis
        page_ranges = []
        for start_page in range(0, total_pages, pages_per_chunk):
            end_page = min(start_page + pages_per_chunk - 1, total_pages - 1)
            page_ranges.append({
                "start": start_page + 1,  # 1-indexed for human readability
                "end": end_page + 1,
                "range_text": f"Pages {start_page+1}-{end_page+1} of {total_pages}"
            })
        
        doc.close()
        
        # Process each chunk
        analysis_results = []
        
        for idx, page_range in enumerate(page_ranges):
            st.info(f"Analyzing chunk {idx+1}/{len(page_ranges)}: {page_range['range_text']}...")
            
            chunk_prompt = f"""You are an expert in educational content development for CBSE curriculum.
This is the user's OWN CONTENT being used for EDUCATIONAL PURPOSES ONLY.

IMPORTANT: You are analyzing CHUNK {idx+1} of {len(page_ranges)} ({page_range['range_text']}) from a book chapter for **{grade_level} (CBSE)**.
This is just a PORTION of the full chapter - focus only on this section.

**FOCUS ONLY ON PAGES {page_range['start']} to {page_range['end']} of the PDF.**

You are extracting information relevant for: {content_type.upper()} CONTENT

Please analyze these specific pages and extract:
* Key concepts, topics, and terminology relevant to {content_type}
* Important facts, examples, and explanations
* For any images, their content and relevance
* Any specific information that would be useful for creating {content_type} content

Format your analysis in Markdown. This is just an intermediate step - don't create final content yet.
"""
            
            try:
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=32768,
                    temperature=0.7,
                )
                
                # Send the full PDF but instruct to focus on specific pages
                response = model.generate_content(
                    [uploaded_file, chunk_prompt],
                    generation_config=generation_config
                )
                
                # Check for copyright detection with fallback
                if response.candidates and response.candidates[0].finish_reason == 4:
                    st.warning(f"Copyright detection on chunk {idx+1}. Trying with text-only fallback...")
                    
                    # Extract just the text for this page range as fallback
                    chunk_text = ""
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    for page_num in range(page_range['start']-1, page_range['end']):
                        page = doc.load_page(page_num)
                        chunk_text += page.get_text()
                    doc.close()
                    
                    # Modify prompt to indicate images won't be available
                    text_only_prompt = chunk_prompt + f"""

**NOTE: This is now processing text-only due to copyright concerns with the full PDF.**

**Text from these pages:**
'''
{chunk_text}
'''
"""
                    
                    # Try again with text-only
                    response = model.generate_content(
                        [text_only_prompt],
                        generation_config=generation_config
                    )
                
                if hasattr(response, 'text') and response.text:
                    analysis_chunk = response.text
                    analysis_results.append(analysis_chunk)
                else:
                    # Handle alternative response format
                    if response.candidates and hasattr(response.candidates[0], 'content') and response.candidates[0].content:
                        parts = response.candidates[0].content.parts
                        if parts:
                            analysis_chunk = ''.join([part.text for part in parts if hasattr(part, 'text')])
                            analysis_results.append(analysis_chunk)
                        else:
                            analysis_results.append(f"[Error processing chunk {idx+1}]")
                    else:
                        analysis_results.append(f"[Error processing chunk {idx+1}]")
                        
            except Exception as chunk_e:
                st.warning(f"Error processing chunk {idx+1}: {chunk_e}")
                analysis_results.append(f"[Error processing chunk {idx+1}: {chunk_e}]")
        
        # Combine chunk analyses
        combined_analyses = "\n\n".join(analysis_results)
        
        # Get the specific prompt for this content type
        specific_prompt = create_specific_prompt(content_type, grade_level, model_progression_text, subject_type)
        
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
            integration_config = genai.types.GenerationConfig(
                max_output_tokens=65536,
                temperature=0.4,  # Lower temperature for more coherent integration
            )
            
            final_response = model.generate_content(
                [integration_prompt],
                generation_config=integration_config
            )
            
            if hasattr(final_response, 'text') and final_response.text:
                final_content = final_response.text
            else:
                # Handle alternative response format
                if final_response.candidates and hasattr(final_response.candidates[0], 'content') and final_response.candidates[0].content:
                    parts = final_response.candidates[0].content.parts
                    if parts:
                        final_content = ''.join([part.text for part in parts if hasattr(part, 'text')])
                    else:
                        raise Exception("No content parts found in final integration response")
                else:
                    raise Exception("No valid text content found in final integration response")
            
            # Clean up resources
            try:
                genai.delete_file(uploaded_file.name)
                st.info(f"Temporary file '{uploaded_file.display_name}' deleted from Gemini.")
            except Exception as e_del:
                st.warning(f"Could not delete temporary file '{uploaded_file.display_name}' from Gemini: {e_del}")
            
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()
                    
            return final_content, "Generated successfully using chunked approach."
            
        except Exception as integration_e:
            st.error(f"Error during final integration: {integration_e}")
            
            # Clean up resources
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
            
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()
                
            # Return the combined chunks without final integration
            return combined_result, "Partial analysis complete - final integration failed."
            
    except Exception as e:
        st.error(f"Error during chunked analysis: {e}")
        
        # Clean up resources
        if 'uploaded_file' in locals():
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
        
        if 'temp_pdf_path' in locals() and temp_pdf_path.exists():
            temp_pdf_path.unlink()
        
        return None, f"Error during chunked analysis: {str(e)}"

# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("📚 Book Chapter Improver Tool (with EeeBee) ✨")

st.markdown("""
Upload your book chapter in PDF format. This tool will analyze it using EeeBee
based on the 'Model Chapter Progression and Elements' and suggest improvements.
Select which part of the content you want to generate.
""")

# Grade Level Selector
grade_options = [f"Grade {i}" for i in range(1, 13)] # Grades 1-12
selected_grade = st.selectbox("Select Target Grade Level (CBSE):", grade_options, index=8) # Default to Grade 9

# Subject Type Selector
subject_type = st.selectbox(
    "Select Subject Type:",
    ["General (Uses Model Chapter Progression)", "Mathematics"],
    help="Choose 'Mathematics' for math-specific content structure or 'General' for other subjects."
)

# Analysis Method Selector
analysis_method = st.radio(
    "Choose Analysis Method:",
    ["Standard (Full Document)", "Chunked (For Complex Documents)"],
    help="Use 'Chunked' method if you encounter copyright errors with the standard method."
)

# Load Model Chapter Progression
model_progression = load_model_chapter_progression()

if model_progression:
    st.sidebar.subheader("Model Chapter Progression:")
    st.sidebar.text_area("Model Details", model_progression, height=300, disabled=True)

    uploaded_file_st = st.file_uploader("Upload your chapter (PDF only)", type="pdf")

    if uploaded_file_st is not None:
        st.info(f"Processing '{uploaded_file_st.name}' for {selected_grade}...")
        
        # Get PDF bytes for processing
        pdf_bytes = uploaded_file_st.getvalue()

        # Create columns for the buttons
        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)
        
        # Create session state to store generated content
        if 'chapter_content' not in st.session_state:
            st.session_state.chapter_content = None
        if 'exercises' not in st.session_state:
            st.session_state.exercises = None
        if 'skill_activities' not in st.session_state:
            st.session_state.skill_activities = None
        if 'art_learning' not in st.session_state:
            st.session_state.art_learning = None

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
            with st.spinner(f"🧠 Generating Chapter Content for {selected_grade}..."):
                content, message = generate_specific_content("chapter", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, subject_type, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
                if content:
                    st.session_state.chapter_content = content
                    st.success(f"✅ Chapter Content generated successfully! {message}")
                    st.subheader("Chapter Content:")
                    st.markdown(st.session_state.chapter_content)
                    # Download button for this content only
                    doc = create_word_document(st.session_state.chapter_content)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    st.download_button(
                        label="📥 Download Chapter Content as Word (.docx)",
                        data=doc_io,
                        file_name=f"chapter_content_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error(f"Failed to generate Chapter Content: {message}")
        
        if generate_exercises:
            with st.spinner(f"🧠 Generating Exercises for {selected_grade}..."):
                content, message = generate_specific_content("exercises", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, subject_type, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
                if content:
                    st.session_state.exercises = content
                    st.success(f"✅ Exercises generated successfully! {message}")
                    st.subheader("Exercises:")
                    st.markdown(st.session_state.exercises)
                    # Download button for this content only
                    doc = create_word_document(st.session_state.exercises)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    st.download_button(
                        label="📥 Download Exercises as Word (.docx)",
                        data=doc_io,
                        file_name=f"exercises_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error(f"Failed to generate Exercises: {message}")
        
        if generate_skills:
            with st.spinner(f"🧠 Generating Skill Activities for {selected_grade}..."):
                content, message = generate_specific_content("skills", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, subject_type, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
                if content:
                    st.session_state.skill_activities = content
                    st.success(f"✅ Skill Activities generated successfully! {message}")
                    st.subheader("Skill Activities:")
                    st.markdown(st.session_state.skill_activities)
                    # Download button for this content only
                    doc = create_word_document(st.session_state.skill_activities)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    st.download_button(
                        label="📥 Download Skill Activities as Word (.docx)",
                        data=doc_io,
                        file_name=f"skill_activities_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error(f"Failed to generate Skill Activities: {message}")
        
        if generate_art:
            with st.spinner(f"🧠 Generating Art-Integrated Learning for {selected_grade}..."):
                content, message = generate_specific_content("art", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, subject_type, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
                if content:
                    st.session_state.art_learning = content
                    st.success(f"✅ Art-Integrated Learning generated successfully! {message}")
                    st.subheader("Art-Integrated Learning:")
                    st.markdown(st.session_state.art_learning)
                    # Download button for this content only
                    doc = create_word_document(st.session_state.art_learning)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    st.download_button(
                        label="📥 Download Art-Integrated Learning as Word (.docx)",
                        data=doc_io,
                        file_name=f"art_learning_{uploaded_file_st.name.replace('.pdf', '.docx')}",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error(f"Failed to generate Art-Integrated Learning: {message}")
        
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

st.sidebar.markdown("---")
st.sidebar.info("This app now uses the EeeBee API.")
