import streamlit as st
import google.generativeai as genai
from docx import Document
import io
import json
import pathlib

# Get Google API key from Streamlit secrets
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("""
    🔑 **Google API Key Not Found!**
    
    Please add your Google API key to Streamlit secrets.
    See instructions in app.py for details.
    """)
    st.stop()

# Initialize Google Gemini Client
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-2.5-pro-preview-05-06")
except Exception as e:
    st.error(f"Error configuring Google Gemini client: {e}")
    st.stop()

# --- Helper Functions ---

def generate_ai_curriculum(grade_level):
    """Generates age-appropriate AI curriculum for a specific grade level"""
    
    # Official CBSE AI curriculum summary for reference
    official_curriculum_9_12 = """
**Official CBSE AI Curriculum (Classes 9-12):**
- **Class 9 (AI Readiness)**: Introduction to AI, AI Project Cycle, Neural Networks, Python Basics
- **Class 10 (AI Foundations)**: Advanced Python, Data Science, Computer Vision, NLP, Model Evaluation
- **Class 11 (AI Explorer)**: Python Lv-2 (NumPy/Pandas/sklearn), ML Algorithms, Applied NLP, AI Ethics
- **Class 12 (AI Innovate)**: Capstone Project, Model Lifecycle, Data Storytelling

Our curriculum for Classes 1-8 must prepare students for this official progression.
"""
    
    prompt = f"""You are an expert in educational curriculum development, specifically for AI education in schools.
You need to create a comprehensive AI curriculum for **{grade_level} (CBSE)**.

**CRITICAL CONTEXT - Official CBSE AI Curriculum for Classes 9-12:**
{official_curriculum_9_12}

**YOUR TASK**: Create a curriculum for {grade_level} that will prepare students for the official CBSE AI curriculum starting in Class 9.

**IMPORTANT GUIDELINES:**

1. **Age Appropriateness**: The content must be suitable for {grade_level} students' cognitive development level
2. **Progressive Learning**: Build on concepts from previous grades (if applicable)
3. **Practical Approach**: Include hands-on activities, projects, and real-world applications
4. **NCERT/NEP 2020 Alignment**: Follow Indian education standards and 21st-century skills framework
5. **Safety and Ethics**: Include age-appropriate discussions on AI ethics and digital citizenship
6. **Pre-Python Foundation**: For grades 1-8, build computational thinking skills that will prepare students for Python programming in Class 9

**CURRICULUM STRUCTURE TO GENERATE:**

## AI Curriculum for {grade_level}

### 1. **Course Overview**
- Total duration: Academic year (April to March)
- Hours per week: 2 periods (suggested)
- Assessment approach
- Connection to future learning (how this prepares for Classes 9-12 AI curriculum)

### 2. **Learning Objectives**
- List 8-10 specific, measurable objectives appropriate for {grade_level}
- Use action verbs aligned with Bloom's Taxonomy
- Include both conceptual understanding and practical skills
- Show clear progression towards Class 9 AI readiness

### 3. **Units/Chapters** (Generate 6-8 units)
For each unit, provide:
- Unit Title
- Duration (in weeks)
- Key Concepts (3-5 concepts)
- Learning Outcomes
- Suggested Activities/Projects
- Integration with other subjects (Math, Science, Language, etc.)
- Connection to future AI concepts (Classes 9-12)

### 4. **Detailed Chapter Breakdown**
For each chapter, include:
- Chapter name and number
- Subtopics to be covered
- Estimated periods needed
- Key vocabulary/terms
- Prerequisite knowledge
- How it builds towards Python/AI concepts in Class 9

### 5. **Practical Components**
- List of hands-on activities
- Project ideas (individual and group)
- Tools/platforms to be used (age-appropriate)
- Unplugged activities (no computer required)
- Computational thinking exercises

### 6. **Assessment Framework**
- Formative assessment strategies
- Summative assessment ideas
- Project-based assessments
- Rubrics outline
- Portfolio development (preparing for Class 9-12 requirements)

### 7. **Resources Required**
- Hardware requirements (minimal)
- Software/apps (free/open-source preferred)
- Other materials
- Transition tools for Class 9 (if Grade 8)

### 8. **Teacher Guidelines**
- Pedagogical approach
- Differentiation strategies
- Common misconceptions to address
- Professional development suggestions

### 9. **Parent/Guardian Involvement**
- How parents can support AI learning at home
- Safety guidelines
- Career awareness in AI field

### 10. **Cross-curricular Connections**
- Integration with Mathematics
- Integration with Science
- Integration with Languages
- Integration with Social Studies
- Integration with Arts

### 11. **Bridge to Class 9**
- Skills that directly prepare for Python programming
- Concepts that lead to understanding AI Project Cycle
- Foundations for Neural Networks understanding
- Preparation for formal AI education

**IMPORTANT NOTES:**
- For Grades 1-3: Focus on AI awareness, pattern recognition, simple algorithms through games and stories
- For Grades 4-5: Introduction to basic programming concepts, simple AI applications, flowcharts
- For Grades 6-8: More structured programming, understanding AI concepts, creating simple AI projects, pre-Python logic

**SPIRAL PROGRESSION**: Remember that the official CBSE curriculum follows spiral progression where "concepts seeded in 9 are coded in 10 and formalised in 11." Your curriculum should establish the earliest seeds of these concepts.

Generate a comprehensive curriculum that is engaging, age-appropriate, and builds strong foundational understanding of AI concepts while preparing students for the official CBSE AI curriculum in Classes 9-12.

Format the output in Markdown with clear headings and structure.
"""
    
    try:
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=32768,
            temperature=0.7,
        )
        
        response = model.generate_content(
            [prompt],
            generation_config=generation_config
        )
        
        if hasattr(response, 'text') and response.text:
            return response.text
        else:
            return "Error: Could not generate curriculum"
            
    except Exception as e:
        st.error(f"Error generating curriculum: {e}")
        return None

def generate_ai_chapter(grade_level, chapter_info, curriculum_context):
    """Generates a complete chapter for AI textbook based on curriculum"""
    
    # Extract grade number for conditional logic
    grade_num = int(grade_level.split()[-1])
    
    # Official curriculum reference
    official_curriculum_info = """
**Official CBSE AI Progression (Classes 9-12):**
- Class 9: Python basics, AI Project Cycle, Neural Networks introduction
- Class 10: Data Science, Computer Vision, NLP basics
- Class 11: NumPy/Pandas/sklearn, ML algorithms, AI Ethics
- Class 12: Capstone projects, MLOps, Data Storytelling
"""
    
    prompt = f"""You are an expert in creating educational content for AI education, specifically for school students.
You need to create a complete chapter for an AI textbook for **{grade_level} (CBSE)**.

**CHAPTER INFORMATION:**
{chapter_info}

**CURRICULUM CONTEXT:**
{curriculum_context}

**IMPORTANT CONTEXT:**
{official_curriculum_info}

This chapter must prepare students for the official CBSE AI curriculum starting in Class 9.

**CHAPTER REQUIREMENTS:**

Create a comprehensive chapter following this structure:

## 1. **Chapter Opening**
- **Chapter Title**: Engaging and age-appropriate
- **Learning Objectives**: 3-5 clear objectives using action verbs
- **Chapter Overview**: Brief introduction (100-150 words)
- **Real-world Connection**: How AI relates to students' daily life
- **Future Learning Path**: Brief note on how this connects to Classes 9-12 AI learning
- **Chapter Mascot Introduction**: Create a friendly AI character/mascot for this grade level

## 2. **Warm-up Activity** (200-300 words)
- An engaging unplugged activity to introduce the concept
- Should be fun and require no computers
- Include clear instructions
- Connect to computational thinking skills

## 3. **Core Content Sections** (2000-3000 words total)
For each main concept:
- **Concept Introduction**: Simple, clear explanation with examples
- **Let's Understand**: Detailed explanation with analogies
- **Try It Out**: Hands-on activity or demonstration
- **Real-life Examples**: Age-appropriate applications
- **Visual Learning**: Detailed image/diagram descriptions
- **Fun Facts**: Interesting AI facts for this age group
- **Think and Discuss**: Questions to spark curiosity
- **Future Connection**: How this concept relates to Classes 9-12 learning

## 4. **Activities Section** (1000-1500 words)
Include 3-4 activities:
- **Activity 1**: Unplugged activity (no computer)
- **Activity 2**: Computer-based activity (if appropriate for grade)
- **Activity 3**: Group project
- **Activity 4**: Creative expression (art, story, etc.)

Each activity should have:
- Clear objectives
- Materials needed
- Step-by-step instructions
- Expected outcomes
- Extension ideas
- Computational thinking skills developed

## 5. **Let's Practice** (500-800 words)
Age-appropriate exercises:
- Fill in the blanks (5-8 questions)
- True/False with explanations (5 questions)
- Match the following (1 set)
- Short answer questions (5-7 questions)
- Think and apply questions (3-5 questions)
- Creative tasks (2-3 tasks)
- Pre-coding logic puzzles (for grades 6-8)

## 6. **Project Time** (300-500 words)
One comprehensive project that:
- Integrates chapter concepts
- Encourages creativity
- Can be done individually or in groups
- Has clear rubrics
- Builds skills needed for AI Project Cycle (Class 9)

## 7. **AI Ethics Corner** (200-300 words)
Age-appropriate discussion on:
- Responsible AI use
- Digital citizenship
- Safety online
- Respecting others' work
- Bias awareness (grades 6-8)

## 8. **Cross-curricular Connections** (200-300 words)
Show how this chapter connects to:
- Mathematics (especially important for future Python/ML)
- Science
- Language
- Social Studies
- Arts

## 9. **Parent/Guardian Section** (150-200 words)
- How to support learning at home
- Conversation starters
- Safety tips
- Career awareness in AI

## 10. **Chapter Summary** (200-300 words)
- Key points recap
- Visual summary/mind map description
- What's coming next
- How this prepares for next grade

## 11. **Glossary**
Define all technical terms in simple language
Include pronunciation guides for technical terms

## 12. **Additional Resources**
- Recommended books (age-appropriate)
- Safe websites
- Educational apps/games
- Future learning resources (Classes 9-12 preview for Grade 8)

**IMPORTANT GUIDELINES:**
1. **Language**: Use simple, clear language appropriate for {grade_level}
2. **Examples**: Use examples from students' daily life
3. **Engagement**: Include stories, games, and interactive elements
4. **Visuals**: Describe many colorful, engaging illustrations
5. **Safety**: Always emphasize safe and responsible AI use
6. **Inclusivity**: Use diverse names and examples
7. **No Prerequisites**: Don't assume prior technical knowledge
8. **Progressive Skills**: Build computational thinking, pattern recognition, and logical reasoning

**AGE-SPECIFIC NOTES:**
- Grades 1-3: Use stories, games, simple patterns, lots of pictures
- Grades 4-5: Introduce basic logic, simple programming concepts, flowcharts
- Grades 6-8: More structured content, basic coding concepts, pre-Python activities

**SPECIAL FOCUS FOR GRADE 8**: Include "Getting Ready for Class 9 AI" sections that preview Python concepts, AI Project Cycle, and formal AI education.

Generate a complete, engaging chapter that makes AI learning fun and accessible for {grade_level} students while building foundations for the official CBSE AI curriculum.

Format in Markdown with clear headings and sections.
"""
    
    try:
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=65536,
            temperature=0.7,
        )
        
        response = model.generate_content(
            [prompt],
            generation_config=generation_config
        )
        
        if hasattr(response, 'text') and response.text:
            return response.text
        else:
            return "Error: Could not generate chapter"
            
    except Exception as e:
        st.error(f"Error generating chapter: {e}")
        return None

def create_word_document(content):
    """Creates a Word document from the markdown content"""
    doc = Document()
    
    # Basic markdown to docx conversion
    lines = content.split('\n')
    
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
        elif line.startswith("#### "):
            doc.add_heading(line[5:], level=4)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:], style='List Bullet')
        else:
            doc.add_paragraph(line)
            
    return doc

def save_curriculum_to_session(grade, curriculum):
    """Saves curriculum to session state"""
    if 'curricula' not in st.session_state:
        st.session_state.curricula = {}
    st.session_state.curricula[grade] = curriculum

def save_chapter_to_session(grade, chapter_num, chapter_content):
    """Saves chapter to session state"""
    if 'chapters' not in st.session_state:
        st.session_state.chapters = {}
    if grade not in st.session_state.chapters:
        st.session_state.chapters[grade] = {}
    st.session_state.chapters[grade][chapter_num] = chapter_content

# --- Streamlit App ---
st.set_page_config(page_title="AI Curriculum Generator for CBSE", layout="wide")

st.title("🤖 AI Curriculum & Textbook Generator for CBSE (Classes 1-8) 📚")

st.markdown("""
This tool helps create age-appropriate AI curriculum and textbook chapters for CBSE classes 1-8.
Since CBSE already has curriculum for classes 9-12, we focus on the primary and middle school levels.
""")

# Add curriculum alignment information
with st.expander("📌 How This Aligns with Official CBSE AI Curriculum (Classes 9-12)"):
    st.markdown("""
    ### 🎯 Progressive Learning Path
    
    Our generated curriculum for Classes 1-8 builds essential foundations for the official CBSE AI curriculum:
    
    **Classes 1-3: AI Awareness**
    - Pattern recognition through games and stories
    - Understanding AI in daily life
    - Basic computational thinking
    - → *Prepares for AI concepts in Class 9*
    
    **Classes 4-5: Logical Thinking**
    - Introduction to algorithms and flowcharts
    - Simple programming concepts (unplugged)
    - Problem-solving strategies
    - → *Foundation for Python programming in Class 9*
    
    **Classes 6-8: Pre-coding Skills**
    - Structured programming logic
    - Understanding data and patterns
    - Introduction to AI applications
    - → *Direct preparation for AI Project Cycle and Python basics*
    
    **Grade 8 Special Focus:**
    - Preview of Python concepts
    - Introduction to AI Project Cycle methodology
    - Preparation for formal AI education
    
    ### 🔄 Spiral Progression
    Following CBSE's approach where "concepts seeded in 9 are coded in 10 and formalised in 11",
    we introduce the earliest seeds of these concepts in Classes 1-8.
    
    ### ✅ Key Skills Developed
    - **Computational Thinking**: Essential for programming
    - **Pattern Recognition**: Core to understanding AI/ML
    - **Ethical AI Use**: Foundation for responsible AI development
    - **Problem Solving**: Preparation for AI Project Cycle
    - **Data Literacy**: Understanding information and patterns
    """)

# Create tabs
tab1, tab2, tab3 = st.tabs(["📋 Generate Curriculum", "📖 Generate Chapters", "📥 Download Materials"])

with tab1:
    st.header("Generate AI Curriculum")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_grade = st.selectbox(
            "Select Grade Level:",
            [f"Grade {i}" for i in range(1, 9)],
            help="Choose the grade for which you want to generate AI curriculum"
        )
        
        generate_curriculum_btn = st.button("🎯 Generate Curriculum", key="gen_curr")
        
        if generate_curriculum_btn:
            with st.spinner(f"Generating AI curriculum for {selected_grade}..."):
                curriculum = generate_ai_curriculum(selected_grade)
                
                if curriculum:
                    save_curriculum_to_session(selected_grade, curriculum)
                    st.success(f"✅ Curriculum generated successfully for {selected_grade}!")
                    
                    # Display curriculum
                    st.markdown("---")
                    st.markdown(curriculum)
                    
                    # Download button
                    doc = create_word_document(curriculum)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    
                    st.download_button(
                        label="📥 Download Curriculum as Word Document",
                        data=doc_io,
                        file_name=f"AI_Curriculum_{selected_grade.replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error("Failed to generate curriculum. Please try again.")
    
    with col2:
        st.info("""
        **Curriculum Features:**
        - Age-appropriate content
        - Progressive learning path
        - Hands-on activities
        - Cross-curricular integration
        - Safety and ethics focus
        - NEP 2020 aligned
        """)

with tab2:
    st.header("Generate AI Textbook Chapters")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        chapter_grade = st.selectbox(
            "Select Grade Level:",
            [f"Grade {i}" for i in range(1, 9)],
            key="chapter_grade",
            help="Choose the grade for which you want to generate a chapter"
        )
        
        # Check if curriculum exists for this grade
        if 'curricula' in st.session_state and chapter_grade in st.session_state.curricula:
            st.success(f"✓ Curriculum found for {chapter_grade}")
            curriculum_context = st.session_state.curricula[chapter_grade][:1000] + "..."  # First 1000 chars
        else:
            st.warning(f"⚠️ No curriculum found for {chapter_grade}. Please generate curriculum first in the 'Generate Curriculum' tab.")
            curriculum_context = "General AI curriculum for this grade level"
        
        chapter_info = st.text_area(
            "Enter Chapter Information:",
            placeholder="""Example:
Chapter 3: Understanding Patterns with AI
- Introduction to patterns in daily life
- How AI recognizes patterns
- Simple pattern games and activities""",
            height=150
        )
        
        generate_chapter_btn = st.button("📝 Generate Chapter", key="gen_chapter")
        
        if generate_chapter_btn and chapter_info:
            with st.spinner(f"Generating AI chapter for {chapter_grade}..."):
                chapter_content = generate_ai_chapter(chapter_grade, chapter_info, curriculum_context)
                
                if chapter_content:
                    # Extract chapter number from info if possible
                    chapter_num = "1"  # Default
                    if "Chapter" in chapter_info and ":" in chapter_info:
                        try:
                            chapter_num = chapter_info.split("Chapter")[1].split(":")[0].strip()
                        except:
                            pass
                    
                    save_chapter_to_session(chapter_grade, chapter_num, chapter_content)
                    st.success(f"✅ Chapter generated successfully for {chapter_grade}!")
                    
                    # Display chapter
                    st.markdown("---")
                    st.markdown(chapter_content)
                    
                    # Download button
                    doc = create_word_document(chapter_content)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    
                    st.download_button(
                        label="📥 Download Chapter as Word Document",
                        data=doc_io,
                        file_name=f"AI_Chapter_{chapter_num}_{chapter_grade.replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error("Failed to generate chapter. Please try again.")
        elif generate_chapter_btn:
            st.error("Please enter chapter information before generating.")
    
    with col2:
        st.info("""
        **Chapter Features:**
        - Engaging opening
        - Clear learning objectives
        - Interactive activities
        - Real-world connections
        - Ethics corner
        - Parent section
        - Age-appropriate exercises
        """)

with tab3:
    st.header("Download Generated Materials")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Available Curricula")
        if 'curricula' in st.session_state and st.session_state.curricula:
            for grade, curriculum in st.session_state.curricula.items():
                st.write(f"✓ {grade}")
                
                doc = create_word_document(curriculum)
                doc_io = io.BytesIO()
                doc.save(doc_io)
                doc_io.seek(0)
                
                st.download_button(
                    label=f"Download {grade} Curriculum",
                    data=doc_io,
                    file_name=f"AI_Curriculum_{grade.replace(' ', '_')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"download_curr_{grade}"
                )
        else:
            st.info("No curricula generated yet.")
    
    with col2:
        st.subheader("📖 Available Chapters")
        if 'chapters' in st.session_state and st.session_state.chapters:
            for grade, chapters in st.session_state.chapters.items():
                st.write(f"**{grade}:**")
                for chapter_num, content in chapters.items():
                    st.write(f"  ✓ Chapter {chapter_num}")
                    
                    doc = create_word_document(content)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    
                    st.download_button(
                        label=f"Download Chapter {chapter_num}",
                        data=doc_io,
                        file_name=f"AI_Chapter_{chapter_num}_{grade.replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"download_ch_{grade}_{chapter_num}"
                    )
        else:
            st.info("No chapters generated yet.")

# Sidebar
st.sidebar.header("About This Tool")
st.sidebar.markdown("""
This tool generates comprehensive AI curriculum and textbook content for CBSE classes 1-8.

**Features:**
- 🎯 Grade-specific curriculum
- 📚 Complete chapter generation
- 🎨 Age-appropriate content
- 🔧 Hands-on activities
- 🌐 Cross-curricular integration
- 🛡️ Ethics and safety focus

**Workflow:**
1. Generate curriculum for a grade
2. Use curriculum to generate chapters
3. Download materials as Word documents

**Note:** This tool complements the official CBSE AI curriculum for classes 9-12.
""")

st.sidebar.markdown("---")
st.sidebar.header("📊 Official CBSE AI Curriculum (9-12)")
st.sidebar.markdown("""
**Class 9 - AI Readiness**
- Introduction to AI
- AI Project Cycle
- Neural Networks
- Python Basics

**Class 10 - AI Foundations**
- Advanced Python
- Data Science
- Computer Vision
- NLP
- Model Evaluation

**Class 11 - AI Explorer**
- NumPy/Pandas/sklearn
- ML Algorithms
- Applied NLP
- AI Ethics & Bias

**Class 12 - AI Innovate**
- Capstone Project
- Model Lifecycle
- Data Storytelling
""")

st.sidebar.markdown("---")
st.sidebar.info("Powered by Google Gemini AI")
