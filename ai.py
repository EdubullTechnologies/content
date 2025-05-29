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

# UAE Curriculum Structure
UAE_CURRICULUM_STRUCTURE = {
    "Kindergarten": {
        "age": "4-5",
        "focus": "Introduction to AI through stories and play",
        "themes": ["What is AI?", "People and Machines", "AI in Our World", "Talking to Machines", "Learning and Helping", "Be Kind with AI"]
    },
    "Cycle 1": {
        "grades": "1-4",
        "focus": "Understanding differences between machines and humans, digital thinking skills, AI applications",
        "core_areas": ["Foundational concepts", "Digital thinking", "AI recognition", "Basic ethics"]
    },
    "Cycle 2": {
        "grades": "5-8",
        "focus": "Designing and evaluating AI systems, learning about bias and algorithms, ethical AI use",
        "core_areas": ["AI design", "Algorithms", "Bias awareness", "Ethical considerations", "Data understanding"]
    },
    "Cycle 3": {
        "grades": "9-12",
        "focus": "Preparing for higher education and careers, command engineering, real-world scenarios",
        "core_areas": ["Advanced AI concepts", "Command engineering", "Real-world applications", "Career preparation", "Innovation"]
    }
}

# --- Helper Functions ---

def generate_uae_curriculum(level, cycle_info):
    """Generates UAE-aligned AI curriculum for a specific level"""
    
    prompt = f"""You are an expert in educational curriculum development, specifically for AI education in UAE schools.
You need to create a comprehensive AI curriculum for **{level}** following UAE's AI curriculum framework.

**UAE AI CURRICULUM FRAMEWORK:**
The UAE AI curriculum encompasses seven core areas:
1. Foundational concepts
2. Data and algorithms
3. Software usage
4. Ethical awareness
5. Real-world applications
6. Innovation and project design
7. Policies and community engagement

**SPECIFIC LEVEL INFORMATION:**
{json.dumps(cycle_info, indent=2)}

**CURRICULUM REQUIREMENTS:**

## 1. **Course Overview**
- Age group/grades covered
- Integration with Computing, Creative Design, and Innovation subject
- Total hours per week (within existing subject hours)
- Assessment approach aligned with UAE standards

## 2. **Learning Objectives**
- 8-10 specific, measurable objectives for this level
- Aligned with UAE's seven core AI areas
- Age-appropriate and culturally relevant
- Focus on practical skills and ethical awareness

## 3. **Units/Modules** (Generate 6-8 units)
For each unit:
- Unit title (English and Arabic consideration)
- Duration (in weeks)
- Key concepts aligned with UAE framework
- Learning outcomes
- Integration with existing subjects
- Cultural relevance and local examples

## 4. **Teaching Methodology**
Based on the level:
{"- Kindergarten: Stories, play-based learning, interactive activities" if level == "Kindergarten" else ""}
{"- Cycle 1: Hands-on activities, digital thinking games, simple projects" if "Cycle 1" in level else ""}
{"- Cycle 2: Project-based learning, AI system design, ethical discussions" if "Cycle 2" in level else ""}
{"- Cycle 3: Real-world scenarios, career exploration, advanced projects" if "Cycle 3" in level else ""}

## 5. **Assessment Framework**
- Formative assessment strategies
- Project-based assessments
- Skills demonstration
- Portfolio development
- Ethical reasoning evaluation

## 6. **Resources and Materials**
- Digital tools and platforms
- Unplugged activities
- Local AI examples (UAE context)
- Bilingual resources consideration

## 7. **Ethical AI Focus**
- Age-appropriate discussions on AI ethics
- Bias awareness activities
- Responsible AI usage
- Digital citizenship in UAE context

## 8. **Real-World Connections**
- UAE's AI initiatives and vision
- Local AI applications
- Career pathways in UAE
- Connection to UAE's digital transformation

## 9. **Innovation Projects**
- Age-appropriate innovation challenges
- Connection to UAE's innovation goals
- Cross-curricular projects
- Community engagement opportunities

## 10. **Teacher Support**
- Professional development needs
- Lesson plan templates
- Activity guides
- Assessment rubrics

Generate a comprehensive curriculum that aligns with UAE's AI education vision, is culturally appropriate, and builds progressive AI literacy.

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

def generate_uae_textbook_unit(level, unit_info, curriculum_context):
    """Generates a textbook unit for UAE AI curriculum"""
    
    # Get example structure from Kindergarten
    kg_example = """
Example from UAE Kindergarten AI Textbook:
- Story-based learning (e.g., "Robo the Helper")
- Interactive activities (coloring, matching, crafts)
- Songs and movement
- Visual aids and characters
- Simple vocabulary introduction
- Assessment through observation
"""
    
    prompt = f"""You are an expert in creating educational content for AI education in UAE schools.
Create a complete textbook unit for **{level}** following UAE's AI curriculum approach.

**UNIT INFORMATION:**
{unit_info}

**CURRICULUM CONTEXT:**
{curriculum_context}

{"**KINDERGARTEN EXAMPLE STRUCTURE:**" + kg_example if level == "Kindergarten" else ""}

**TEXTBOOK UNIT REQUIREMENTS:**

## 1. **Unit Opening**
- Unit title (consider bilingual needs)
- Learning objectives (aligned with UAE curriculum)
- Unit overview (age-appropriate introduction)
- Connection to daily life in UAE
- Visual mascot/character introduction

## 2. **Core Content Structure**

{"### For Kindergarten (Ages 4-5):" if level == "Kindergarten" else ""}
{"- Story-based lesson (like 'Robo the Helper')" if level == "Kindergarten" else ""}
{"- Interactive elements (colors, shapes, sounds)" if level == "Kindergarten" else ""}
{"- Simple vocabulary with visuals" if level == "Kindergarten" else ""}
{"- Play-based activities" if level == "Kindergarten" else ""}

{"### For Cycle 1 (Grades 1-4):" if "Cycle 1" in level else ""}
{"- Engaging narratives with AI concepts" if "Cycle 1" in level else ""}
{"- Hands-on activities and experiments" if "Cycle 1" in level else ""}
{"- Digital thinking challenges" if "Cycle 1" in level else ""}
{"- Simple coding concepts (unplugged)" if "Cycle 1" in level else ""}

{"### For Cycle 2 (Grades 5-8):" if "Cycle 2" in level else ""}
{"- Conceptual explanations with examples" if "Cycle 2" in level else ""}
{"- AI system design activities" if "Cycle 2" in level else ""}
{"- Bias and ethics discussions" if "Cycle 2" in level else ""}
{"- Algorithm exploration" if "Cycle 2" in level else ""}

{"### For Cycle 3 (Grades 9-12):" if "Cycle 3" in level else ""}
{"- Advanced concepts and theories" if "Cycle 3" in level else ""}
{"- Real-world case studies" if "Cycle 3" in level else ""}
{"- Command engineering practice" if "Cycle 3" in level else ""}
{"- Career exploration activities" if "Cycle 3" in level else ""}

## 3. **Activities Section**
Include 3-4 activities appropriate for the level:
- Activity objectives
- Materials needed
- Step-by-step instructions
- Expected outcomes
- Extension ideas
- Group vs individual work

## 4. **Technology Integration**
- Digital tools usage (age-appropriate)
- Unplugged alternatives
- Screen time considerations
- Safe online practices

## 5. **Assessment Strategies**
{"- Observation checklists" if level == "Kindergarten" else ""}
{"- Simple skill demonstrations" if "Cycle 1" in level else ""}
{"- Project-based assessments" if "Cycle 2" in level else ""}
{"- Portfolio development" if "Cycle 3" in level else ""}
- Formative assessment ideas
- Self-assessment tools (age-appropriate)

## 6. **Cultural Integration**
- UAE context and examples
- Local AI applications
- Arabic language considerations
- Cultural values integration

## 7. **Home-School Connection**
- Parent/guardian guidance
- Home activities
- Safety guidelines
- Family engagement ideas

## 8. **Additional Resources**
- Vocabulary list (English/Arabic)
- Visual aids descriptions
- Songs/rhymes (if applicable)
- Digital resources links
- Teacher notes

## 9. **Unit Summary**
- Key concepts recap
- Skills developed
- Connection to next unit
- Celebration of learning

**IMPORTANT GUIDELINES:**
1. Use age-appropriate language
2. Include visual learning elements
3. Ensure cultural sensitivity
4. Balance digital and unplugged activities
5. Focus on ethical AI use
6. Make content engaging and interactive
7. Consider bilingual needs

Generate a complete textbook unit that aligns with UAE's AI curriculum vision and engages students effectively.

Format in Markdown with clear sections and visual descriptions.
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
            return "Error: Could not generate textbook unit"
            
    except Exception as e:
        st.error(f"Error generating textbook unit: {e}")
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

# --- Streamlit App ---
st.set_page_config(page_title="UAE AI Curriculum Generator", layout="wide")

st.title("🇦🇪 UAE AI Curriculum & Textbook Generator 🤖")

st.markdown("""
This tool generates AI curriculum and textbook content aligned with the UAE's AI education framework.
The UAE AI curriculum integrates into existing Computing, Creative Design, and Innovation subjects.
""")

# UAE Curriculum Overview
with st.expander("📋 UAE AI Curriculum Framework Overview"):
    st.markdown("""
    ### 🎯 Seven Core Areas
    1. **Foundational concepts** - Basic AI understanding
    2. **Data and algorithms** - How AI processes information
    3. **Software usage** - Practical AI tools
    4. **Ethical awareness** - Responsible AI use
    5. **Real-world applications** - AI in daily life
    6. **Innovation and project design** - Creating with AI
    7. **Policies and community engagement** - AI in society
    
    ### 📚 Learning Cycles
    
    **🧸 Kindergarten (Ages 4-5)**
    - Introduction through stories and play
    - Simple concepts like "smart machines"
    - Interactive, game-based learning
    
    **📖 Cycle 1 (Grades 1-4)**
    - Understanding machines vs humans
    - Developing digital thinking skills
    - Exploring AI applications
    
    **💻 Cycle 2 (Grades 5-8)**
    - Designing and evaluating AI systems
    - Learning about bias and algorithms
    - Focusing on ethical AI use
    
    **🚀 Cycle 3 (Grades 9-12)**
    - Command engineering
    - Real-world scenarios
    - Career preparation
    
    ### ✨ Key Features
    - Integrated into existing subjects (no extra hours)
    - Focus on ethical and practical skills
    - Comprehensive teacher support materials
    - Age-appropriate progression
    """)

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["📋 Generate Curriculum", "📖 Generate Textbook Units", "📥 Download Materials", "💡 Examples"])

with tab1:
    st.header("Generate UAE AI Curriculum")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_level = st.selectbox(
            "Select Education Level:",
            ["Kindergarten", "Cycle 1 (Grades 1-4)", "Cycle 2 (Grades 5-8)", "Cycle 3 (Grades 9-12)"]
        )
        
        # Get cycle info
        if selected_level == "Kindergarten":
            cycle_info = UAE_CURRICULUM_STRUCTURE["Kindergarten"]
        else:
            cycle_key = selected_level.split(" ")[0] + " " + selected_level.split(" ")[1]
            cycle_info = UAE_CURRICULUM_STRUCTURE[cycle_key]
        
        generate_curriculum_btn = st.button("🎯 Generate Curriculum", key="gen_curr_uae")
        
        if generate_curriculum_btn:
            with st.spinner(f"Generating UAE AI curriculum for {selected_level}..."):
                curriculum = generate_uae_curriculum(selected_level, cycle_info)
                
                if curriculum:
                    # Save to session state
                    if 'uae_curricula' not in st.session_state:
                        st.session_state.uae_curricula = {}
                    st.session_state.uae_curricula[selected_level] = curriculum
                    
                    st.success(f"✅ Curriculum generated successfully for {selected_level}!")
                    
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
                        file_name=f"UAE_AI_Curriculum_{selected_level.replace(' ', '_').replace('(', '').replace(')', '')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
    
    with col2:
        st.info("""
        **UAE Curriculum Features:**
        - Seven core AI areas
        - Age-appropriate content
        - Integrated approach
        - Ethical focus
        - Local context
        - Bilingual considerations
        """)

with tab2:
    st.header("Generate AI Textbook Units")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        textbook_level = st.selectbox(
            "Select Education Level:",
            ["Kindergarten", "Cycle 1 (Grades 1-4)", "Cycle 2 (Grades 5-8)", "Cycle 3 (Grades 9-12)"],
            key="textbook_level"
        )
        
        # Check if curriculum exists
        if 'uae_curricula' in st.session_state and textbook_level in st.session_state.uae_curricula:
            st.success(f"✓ Curriculum found for {textbook_level}")
            curriculum_context = st.session_state.uae_curricula[textbook_level][:1000] + "..."
        else:
            st.warning(f"⚠️ No curriculum found for {textbook_level}. Please generate curriculum first.")
            curriculum_context = "General UAE AI curriculum for this level"
        
        unit_info = st.text_area(
            "Enter Unit Information:",
            placeholder="""Example:
Unit 3: AI in Our Daily Life
- Recognizing AI around us
- Smart devices in UAE
- How AI helps in school and home
- Being safe with AI""",
            height=150
        )
        
        # Show example units based on level
        if textbook_level == "Kindergarten":
            st.caption("Example units: What Is AI?, People and Machines, AI in Our World, Talking to Machines")
        
        generate_unit_btn = st.button("📝 Generate Textbook Unit", key="gen_unit")
        
        if generate_unit_btn and unit_info:
            with st.spinner(f"Generating textbook unit for {textbook_level}..."):
                unit_content = generate_uae_textbook_unit(textbook_level, unit_info, curriculum_context)
                
                if unit_content:
                    # Save to session state
                    if 'uae_units' not in st.session_state:
                        st.session_state.uae_units = {}
                    if textbook_level not in st.session_state.uae_units:
                        st.session_state.uae_units[textbook_level] = {}
                    
                    # Extract unit name
                    unit_name = unit_info.split('\n')[0] if unit_info else "Unit"
                    st.session_state.uae_units[textbook_level][unit_name] = unit_content
                    
                    st.success(f"✅ Textbook unit generated successfully!")
                    
                    # Display unit
                    st.markdown("---")
                    st.markdown(unit_content)
                    
                    # Download button
                    doc = create_word_document(unit_content)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    
                    st.download_button(
                        label="📥 Download Unit as Word Document",
                        data=doc_io,
                        file_name=f"UAE_AI_{textbook_level.replace(' ', '_')}_{unit_name.replace(' ', '_').replace(':', '')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
    
    with col2:
        st.info("""
        **Unit Features:**
        - Story-based learning
        - Interactive activities
        - Cultural integration
        - Ethical discussions
        - Assessment strategies
        - Parent engagement
        """)

with tab3:
    st.header("Download Generated Materials")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Available Curricula")
        if 'uae_curricula' in st.session_state and st.session_state.uae_curricula:
            for level, curriculum in st.session_state.uae_curricula.items():
                st.write(f"✓ {level}")
                
                doc = create_word_document(curriculum)
                doc_io = io.BytesIO()
                doc.save(doc_io)
                doc_io.seek(0)
                
                st.download_button(
                    label=f"Download {level} Curriculum",
                    data=doc_io,
                    file_name=f"UAE_AI_Curriculum_{level.replace(' ', '_').replace('(', '').replace(')', '')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"download_curr_{level}"
                )
        else:
            st.info("No curricula generated yet.")
    
    with col2:
        st.subheader("📖 Available Textbook Units")
        if 'uae_units' in st.session_state and st.session_state.uae_units:
            for level, units in st.session_state.uae_units.items():
                st.write(f"**{level}:**")
                for unit_name, content in units.items():
                    st.write(f"  ✓ {unit_name}")
                    
                    doc = create_word_document(content)
                    doc_io = io.BytesIO()
                    doc.save(doc_io)
                    doc_io.seek(0)
                    
                    st.download_button(
                        label=f"Download {unit_name}",
                        data=doc_io,
                        file_name=f"UAE_AI_{level.replace(' ', '_')}_{unit_name.replace(' ', '_').replace(':', '')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"download_unit_{level}_{unit_name}"
                    )
        else:
            st.info("No textbook units generated yet.")

with tab4:
    st.header("📚 Examples from UAE AI Curriculum")
    
    st.subheader("🧸 Kindergarten Example: 'Robo the Helper'")
    st.markdown("""
    ### Story Summary
    Robo is a friendly robot that helps Leo and his family at home. He turns on lights, 
    reminds Leo to brush his teeth, plays music, and even helps find Leo's lost shoe!
    
    ### Learning Activities
    1. **Color the AI Helpers** - Children color smart devices
    2. **AI vs Not AI Game** - Identify smart helpers
    3. **"I Am a Smart Machine" Song** - Music and movement
    4. **Make Your Own Robo** - Craft activity
    
    ### Assessment
    - Observation checklist
    - "Junior AI Explorer" badges
    - Portfolio of creative work
    """)
    
    st.subheader("💡 Teaching Strategies by Level")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Kindergarten & Cycle 1:**
        - Story-based learning
        - Interactive play
        - Visual aids
        - Songs and rhymes
        - Hands-on crafts
        - Simple vocabulary
        """)
    
    with col2:
        st.markdown("""
        **Cycle 2 & 3:**
        - Project-based learning
        - Ethical discussions
        - Real-world applications
        - Digital tools exploration
        - Career connections
        - Innovation challenges
        """)

# Sidebar
st.sidebar.header("About UAE AI Curriculum")
st.sidebar.markdown("""
The UAE AI curriculum represents a pioneering educational initiative to prepare students for an AI-driven future.

**Key Principles:**
- 🌍 Culturally relevant
- 🤝 Ethically focused
- 💡 Innovation-oriented
- 📚 Integrated learning
- 🎯 Practical skills
- 🌐 Bilingual approach

**Integration:**
AI education is seamlessly integrated into existing subjects:
- Computing
- Creative Design
- Innovation

No additional teaching hours required!
""")

st.sidebar.markdown("---")
st.sidebar.header("🎯 Quick Start Guide")
st.sidebar.markdown("""
1. **Generate Curriculum** first for your chosen level
2. **Create Units** using the curriculum as context
3. **Download Materials** for classroom use
4. **Check Examples** for inspiration

**Recommended Workflow:**
- Start with Kindergarten for foundational concepts
- Progress through cycles for complete coverage
- Customize units for local context
""")

st.sidebar.markdown("---")
st.sidebar.info("Powered by Google Gemini AI")
