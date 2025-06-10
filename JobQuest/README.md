# JobQuest - 90s Style Job Portal

JobQuest is a retro-inspired web application that connects to the "Projet fil rouge" backend to provide job recommendations, CV parsing, and interview simulation with a nostalgic 90s video game aesthetic.

## Features

- **90s Video Game UI**: Complete with scan lines, CRT flicker effects, and retro sound effects
- **CV Parsing**: Upload and analyze CVs using AI to extract skills and experience
- **Job Recommendations**: Get personalized job recommendations based on your CV
- **Interview Simulator**: Practice interviewing for specific job positions with an AI interviewer
- **Job Search**: Search jobs by keywords and browse job listings

## Prerequisites

Before running JobQuest, make sure you have:

1. Python 3.8+ installed
2. PostgreSQL with PostGIS and PostgresML extensions
3. GROQ API key for AI functionality
4. The original "Projet fil rouge" codebase accessible

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/JobQuest.git
   cd JobQuest
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the project root:
   ```
   GROQ_API_KEY=your_groq_api_key
   ```

5. Make sure the PostgreSQL database is set up according to the original "Projet fil rouge" specifications:
   - Database name: projet_fil_rouge
   - Port: 5433
   - Username: postgres
   - Password: postgres

## Configuration

The application assumes the original "Projet fil rouge" project is in the parent directory. If your directory structure is different, you'll need to update the import paths in:

- `/utils/cv_processor.py`
- `/utils/interview_simulator.py`
- `/utils/job_recommender.py`

## Running the Application

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Project Structure

```
JobQuest/
│
├── app.py                 # Main Flask application
├── uploads/               # Temporary storage for uploaded CVs
├── requirements.txt       # Project dependencies
│
├── static/
│   ├── style.css          # 90s-inspired CSS styles
│   └── script.js          # Frontend JavaScript with retro effects
│
├── templates/
│   ├── base.html          # Base template
│   ├── index.html         # Homepage
│   ├── upload_cv.html     # CV upload page
│   ├── job_search.html    # Job search and listing page
│   ├── job_details.html   # Individual job details
│   ├── interview.html     # Interview simulator
│   └── 404.html           # Error page
│
└── utils/
    ├── cv_processor.py    # CV parsing and storage functionality
    ├── job_recommender.py # Job recommendation engine
    └── interview_simulator.py # Interview simulation functionality
```

## How It Works

1. **CV Upload**: When a user uploads their CV, it's processed by the original "Projet fil rouge" CV parser and stored in the PostgreSQL database.

2. **Job Recommendations**: The app connects to the database to retrieve job offers that match the user's profile using embedding similarity.

3. **Interview Simulator**: Uses the LLaMA 3 model via GROQ API to simulate an interviewer based on the job description.

## Customizing the Application

- **Styling**: Modify `static/style.css` to change the application's appearance
- **Frontend Behavior**: Edit `static/script.js` to adjust frontend functionality
- **Page Templates**: Update files in the `templates/` directory to change page layouts

## Troubleshooting

- **Database Connection Issues**: Ensure PostgreSQL is running on port 5433 with the correct username and password
- **API Errors**: Check that your GROQ API key is valid and properly set in the .env file
- **Import Errors**: Verify that the path to the "Projet fil rouge" project is correct

## Requirements

```
flask==2.3.3
psycopg2==2.9.10
psycopg2-binary==2.9.10
sqlalchemy==2.0.37
werkzeug==2.3.7
python-dotenv==1.0.1
langchain==0.3.14
langchain-groq==0.2.3
langchain-core==0.3.29
```

## Credits

This application connects to the "Projet fil rouge" backend which provides:
- CV parsing and storage
- Job data storage and retrieval
- Embedding similarity search for job recommendations
- Interview simulation capabilities

## License

This project is licensed under the MIT License - see the LICENSE file for details.