# A2A Retail Demo 🛍️

## 📋 Project Purpose

This project demonstrates the power of **Google's Agent-to-Agent (A2A) protocol** in building sophisticated multi-agent AI systems. It showcases how specialized AI agents can collaborate seamlessly to solve complex business problems in a retail context.

### Why This Matters

Traditional single-agent AI systems often struggle with diverse tasks that require different types of expertise. This demo illustrates how the A2A protocol enables:

- **Modular AI Architecture**: Each agent specializes in its domain (inventory management vs. customer service)
- **Intelligent Orchestration**: A host agent dynamically routes queries to the right specialist
- **Parallel Processing**: Complex queries are handled by multiple agents simultaneously
- **Real-world Integration**: Demonstrates integration with Google's Vertex AI Search for production-ready capabilities

This approach mirrors how human organizations work - with specialists handling their areas of expertise while collaborating on complex tasks.

## 🚀 Features

- **Multi-Agent Architecture**: Three specialized agents working in harmony
  - **Host Agent**: Intelligent query routing and orchestration
  - **Inventory Agent**: Product search and stock management powered by Vertex AI Search
  - **Customer Service Agent**: Handles store info, policies, and general inquiries
  
- **Advanced Capabilities**:
  - Semantic product search using Vertex AI Search
  - Real-time inventory tracking
  - Parallel agent execution for complex queries
  - Streaming responses for better UX
  - A2A protocol implementation for agent communication

## 🏗️ Architecture

```
                                                          
   Frontend      →  Host Agent      →  Inventory Agent    
   (Mesop)          (Port 8000)        (Port 8001)        
                        ↓              - Vertex AI Search 
                                       - ADK Framework    
                                                              
                        ↓                                     
                                                              
                                       Customer Service    
                                       Agent (Port 8002)   
                                       - LangGraph         
                                       - Gemini Model      
                                                              
```

## 📋 Prerequisites

- Python 3.11+
- Google Cloud Project with:
  - Vertex AI Search API enabled
  - Gemini API access
  - Application Default Credentials configured
- Environment variables:
  - `GOOGLE_API_KEY`: Your Gemini API key
  - `VERTEX_SEARCH_SERVING_CONFIG`: Your Vertex AI Search serving config path

## 🔐 Google Cloud Authentication

### Setting up Authentication

1. **Install Google Cloud CLI** (if not already installed):
   ```bash
   # macOS
   brew install google-cloud-sdk
   
   # Linux/WSL
   curl https://sdk.cloud.google.com | bash
   ```

2. **Authenticate with Google Cloud**:
   ```bash
   # Login to your Google account
   gcloud auth login
   
   # Set your project
   gcloud config set project YOUR_PROJECT_ID
   
   # Set up Application Default Credentials
   gcloud auth application-default login
   ```

3. **Enable Required APIs**:
   ```bash
   # Enable Vertex AI Search
   gcloud services enable discoveryengine.googleapis.com
   
   # Enable other required APIs
   gcloud services enable aiplatform.googleapis.com
   ```

### Important Authentication Notes

- **Application Default Credentials (ADC)**: The `gcloud auth application-default login` command creates credentials that applications can use to authenticate as your user account
- **Service Account (Production)**: For production deployments, use a service account with appropriate permissions instead of user credentials
- **Credentials Location**: ADC credentials are stored at:
  - macOS/Linux: `~/.config/gcloud/application_default_credentials.json`
  - Windows: `%APPDATA%\gcloud\application_default_credentials.json`

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/a2a-retail-demo.git
   cd a2a-retail-demo
   ```

2. **Set up the environment**:
   ```bash
   make setup
   ```
   This will:
   - Create a virtual environment
   - Install all dependencies
   - Create a `.env` file from the example

3. **Configure environment variables**:
   ```bash
   # Edit .env file
   vim .env
   
   # Add your configurations:
   GOOGLE_API_KEY=your-gemini-api-key
   VERTEX_SEARCH_SERVING_CONFIG=projects/YOUR_PROJECT/locations/YOUR_LOCATION/collections/default_collection/dataStores/YOUR_DATASTORE/servingConfigs/default_config
   ```

4. **Verify setup**:
   ```bash
   make check-setup
   ```

## 🚀 Running the Demo

### Quick Start
```bash
make start
```
This starts all agents and the frontend automatically.

### Individual Components
```bash
# Start specific agents
make start-host           # Host agent on port 8000
make start-inventory      # Inventory agent on port 8001  
make start-customer-service  # Customer service agent on port 8002
make start-frontend       # Frontend on port 8080
```

### Access the Application
Open your browser to: `http://localhost:8080`

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test suites
make test-unit          # Unit tests only
make test-integration   # Integration tests
make test-coverage      # With coverage report

# Test A2A communication
make test-a2a
```

## 📁 Project Structure

```
a2a-retail-demo/
├── backend/
│   ├── agents/
│   │   ├── host_agent/         # Orchestrator using ADK
│   │   ├── inventory_agent_a2a/ # Inventory with Vertex Search
│   │   └── customer_service_a2a/ # Customer service with LangGraph
│   ├── utils/
│   │   └── vector_search_store.py # Vertex AI Search integration
│   └── tests/                  # Test suites
├── frontend/
│   └── app.py                  # Mesop UI application
├── scripts/
│   ├── start_a2a_demo.sh      # Startup script
│   └── test_a2a_agents.py     # A2A testing utility
├── .env.example               # Environment template
├── Makefile                   # Task automation
└── requirements.txt           # Python dependencies
```

## 🔧 Development

### Code Quality
```bash
# Lint code
make lint

# Format code
make format
```

### Adding New Agents

1. Create a new agent directory under `backend/agents/`
2. Implement the A2A protocol interface
3. Register with the host agent
4. Add tests

### Debugging

- Check agent logs in the console
- Use `make check-setup` to verify configuration
- Test individual agents with `scripts/test_a2a_agents.py`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📝 Troubleshooting

### Common Issues

1. **"VERTEX_SEARCH_SERVING_CONFIG not set"**
   - Ensure you've configured the `.env` file
   - Format: `projects/{project}/locations/{location}/collections/{collection}/dataStores/{datastore}/servingConfigs/{config}`

2. **Authentication errors**
   - Run `gcloud auth application-default login`
   - Ensure your project has the necessary APIs enabled

3. **Import errors**
   - Verify you're using Python 3.11+
   - Run `make setup` to install dependencies

4. **Agents not responding**
   - Check if all agents are running: `make check-setup`
   - Verify ports 8000-8002 are not in use

## 📜 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Google's A2A Protocol and ADK teams
- Vertex AI Search team
- LangGraph and LangChain communities

---

Built with ❤️ using Google's Agent-to-Agent protocol