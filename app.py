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

def create_specific_prompt(content_type, grade_level, model_progression_text):
    """Creates a prompt focused on a specific content type"""
    
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

1. **Current Concepts** (1500-2000 words minimum)
   The Current Concepts section must include ALL of the following components in order:
   
   a) **Introduction of Concept** (200-300 words)
      - Clear introduction to the main concept(s) from the PDF
      - Engaging opening that sets the context
      - Brief overview of what students will learn
   
   b) **Key Points** (300-400 words)
      - List and explain 5-8 key points related to the concept
      - Use bullet points or numbered lists for clarity
      - Provide detailed explanations for each point
   
   c) **Think About It (Related Real Life)** (150-200 words)
      - Present 2-3 real-life scenarios that connect to the concept
      - Encourage students to think critically about applications
      - Use relatable examples from students' daily experiences
   
   d) **Sub-concept List** (100-150 words)
      - Identify and list all major sub-concepts
      - Provide brief descriptions of each sub-concept
      - Show how sub-concepts relate to the main concept
   
   e) **Content Related Sub-concept with Image Prompt** (400-500 words)
      - Detailed explanation of each sub-concept
      - Include specific image prompts for visual learning
      - Format image prompts as: [PROMPT FOR NEW IMAGE: detailed description]
      - Connect sub-concepts to real-world applications
   
   f) **Summary in Table Format** (200-250 words)
      - Create a comprehensive table summarizing key information
      - Include columns for: Concept, Definition, Example, Application
      - Use Markdown table formatting
   
   g) **Common Misconceptions** (200-300 words)
      - Identify 3-5 common misconceptions about the concept
      - Explain why these misconceptions occur
      - Provide correct explanations to address each misconception
   
   h) **Activity** (150-200 words)
      - Design 1-2 hands-on activities related to the concept
      - Include materials needed and step-by-step instructions
      - Connect activities to learning objectives
   
   i) **Key Terms with Definitions** (200-300 words)
      - List 8-12 important terms from the concept
      - Provide clear, age-appropriate definitions
      - Include pronunciation guides where necessary
   
   j) **Real World Applications** (250-350 words)
      - Provide 4-6 specific real-world applications
      - Include examples from technology, medicine, environment, etc.
      - Explain how the concept impacts society and daily life
   
   k) **Did You Know** (100-150 words)
      - Include 3-4 interesting facts related to the concept
      - Use surprising or fascinating information to engage students
      - Connect facts to the main learning objectives
   
   l) **Check Your Understanding Questions:**
      - 2 MCQ with Bloom's Taxonomy tagging (specify level: Remember, Understand, Apply, Analyze, Evaluate, Create)
      - 2 Short Answer Questions with Bloom's Taxonomy tagging
      - 1 HOT (Higher Order Thinking) Question based on real life
      - 1 Riddle type question related to the concept
      - Include answer keys and explanations for all questions

2. **Hook (with Image Prompt)** (200-300 words)
   - Create an engaging opening that captures student interest
   - Use storytelling, surprising facts, or thought-provoking questions
   - Connect to students' daily experiences or current events
   - Include a detailed image prompt for a compelling visual

3. **Learning Outcome** (150-200 words)
   - List specific, measurable learning objectives
   - Use action verbs (analyze, evaluate, create, etc.)
   - Align with Bloom's Taxonomy levels
   - Connect to CBSE curriculum standards

4. **Real World Connection** (400-600 words)
   - Provide multiple real-world applications of the concepts
   - Include current examples from technology, environment, health, etc.
   - Explain how the concepts impact daily life
   - Connect to career opportunities and future studies

5. **Previous Class Concept** (300-400 words)
   - Thoroughly review prerequisite knowledge
   - Explain how previous concepts build to current learning
   - Provide clear connections and progressions
   - Include brief refresher explanations of key prior concepts

6. **History** (400-500 words)
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
* **Minimum Total Length**: 3000-4000 words for the complete chapter content
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

def generate_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text, use_chunked=False):
    """Generates specific content based on content type"""
    prompt = create_specific_prompt(content_type, grade_level, model_progression_text)
    
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
                return generate_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text, use_chunked=True)
            
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
        return analyze_with_chunked_approach_for_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text)

def analyze_with_chunked_approach_for_specific_content(content_type, pdf_bytes, pdf_filename, grade_level, model_progression_text):
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
        specific_prompt = create_specific_prompt(content_type, grade_level, model_progression_text)
        
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
            genai.delete_file(uploaded_file.name)
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
            
            return None, f"Error during final integration: {str(integration_e)}"
        
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
                content, message = generate_specific_content("chapter", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
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
                content, message = generate_specific_content("exercises", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
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
                content, message = generate_specific_content("skills", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
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
                content, message = generate_specific_content("art", pdf_bytes, uploaded_file_st.name, selected_grade, model_progression, use_chunked=(analysis_method == "Chunked (For Complex Documents)"))
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
