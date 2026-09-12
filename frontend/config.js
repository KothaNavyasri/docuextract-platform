// Configuration for Backend API Base URL
// In production, this can be dynamically overridden or point to the deployed Render/Railway backend URL
const CONFIG = {
  // Default to localhost when running locally, or point to deployed Render backend in production
  API_BASE_URL: window.API_BASE_URL || (
    window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
      ? "http://127.0.0.1:8000/api/v1"
      : "https://docuextract-backend-lmts.onrender.com/api/v1"
  )
};

window.APP_CONFIG = CONFIG;
