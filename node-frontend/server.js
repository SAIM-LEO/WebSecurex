require('dotenv').config({ path: '../.env' });
const express = require('express');
const mongoose = require('mongoose');
const axios = require('axios');
const morgan = require('morgan');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const path = require('path');

const app = express();
const PYTHON = (process.env.PYTHON_BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const JWT_SECRET = process.env.JWT_SECRET || 'websecurex_secret';

function formatAxiosError(err) {
  if (err.response && err.response.data) {
    if (typeof err.response.data === 'string') return err.response.data;
    if (err.response.data.detail) {
      if (typeof err.response.data.detail === 'string') return err.response.data.detail;
      return JSON.stringify(err.response.data.detail);
    }
    if (err.response.data.error) return err.response.data.error;
    return JSON.stringify(err.response.data);
  }
  return err.message || 'Backend communication error';
}

// Schemas
const UserSchema = new mongoose.Schema({
  username:   { type: String, required: true, unique: true, trim: true },
  email:      { type: String, required: true, unique: true, lowercase: true },
  password:   { type: String, required: true },
  created_at: { type: Date, default: Date.now }
});
const User = mongoose.model('User', UserSchema);

const ScanSchema = new mongoose.Schema({
  scan_id:          { type: String, required: true, unique: true },
  user_id:          { type: String, required: true },
  target_url:       { type: String, required: true },
  scan_type:        { type: String, default: 'full' },
  timestamp:        { type: Date, default: Date.now },
  status:           { type: String, default: 'pending' },
  overall_risk:     { type: String, default: null },
  summary:          { type: Object, default: null },
  scans:            { type: Object, default: null },
  scans_run:        { type: [String], default: [] },
  db_type_detected: { type: String, default: null },
  progress:         { type: Number, default: 0 },
  current_phase:    { type: String, default: null },
  overall_score:    { type: Number, default: 0 },
  tool_scores:      { type: Object, default: {} },
  ssl_valid:        { type: Boolean, default: false },
  scan_level:       { type: String, default: 'quick' },
  scan_completed:   { type: Boolean, default: false }
});
const Scan = mongoose.model('Scan', ScanSchema);

// Auth Middleware
function authMiddleware(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'No token provided' });
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    res.status(401).json({ error: 'Invalid or expired token' });
  }
}

app.use(express.json());
app.use(morgan('dev'));
app.use(express.static(path.join(__dirname, 'public')));

// Public Auth Routes
app.post('/auth/signup', async (req, res) => {
  try {
    const { username, email, password } = req.body;
    const existing = await User.findOne({ $or: [{ email }, { username }] });
    if (existing) return res.status(400).json({ error: 'Username or Email already exists' });
    
    const hashedPassword = await bcrypt.hash(password, 10);
    const newUser = new User({ username, email, password: hashedPassword });
    await newUser.save();
    res.json({ message: 'Account created successfully' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    const user = await User.findOne({ email });
    if (!user) return res.status(401).json({ error: 'Invalid credentials' });
    
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) return res.status(401).json({ error: 'Invalid credentials' });
    
    const token = jwt.sign({ userId: user._id, username: user.username }, JWT_SECRET, { expiresIn: '7d' });
    res.json({ token, username: user.username, userId: user._id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Protected Scan Routes
app.post('/scan', authMiddleware, async (req, res) => {
  try {
    const response = await axios.post(`${PYTHON}/api/scan`, { ...req.body, user_id: req.user.userId }, { timeout: 30000 });
    res.json(response.data);
  } catch (err) {
    console.error('Scan proxy error:', formatAxiosError(err));
    res.status(err.response?.status || 500).json({ error: formatAxiosError(err) });
  }
});

app.get('/scan/:id/status', authMiddleware, async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON}/api/scan/${req.params.id}/status`, { timeout: 15000 });
    await Scan.updateOne({ scan_id: req.params.id }, response.data);
    res.json(response.data);
  } catch (err) {
    res.status(err.response?.status || 500).json({ error: formatAxiosError(err) });
  }
});

app.get('/scan/:id/report', authMiddleware, async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON}/api/scan/${req.params.id}/report`, { timeout: 15000 });
    await Scan.updateOne({ scan_id: req.params.id }, response.data);
    res.json(response.data);
  } catch (err) {
    res.status(err.response?.status || 500).json({ error: formatAxiosError(err) });
  }
});

app.get('/history', authMiddleware, async (req, res) => {
  try {
    const history = await Scan.find({ user_id: req.user.userId }).sort({ timestamp: -1 });
    res.json(history);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/scan/:id', authMiddleware, async (req, res) => {
  try {
    const scan = await Scan.findOne({ scan_id: req.params.id, user_id: req.user.userId });
    if (!scan) return res.status(403).json({ error: 'Unauthorized' });
    await axios.delete(`${PYTHON}/api/scan/${req.params.id}`, { timeout: 15000 });
    await Scan.deleteOne({ scan_id: req.params.id });
    res.json({ message: 'Deleted' });
  } catch (err) {
    res.status(err.response?.status || 500).json({ error: formatAxiosError(err) });
  }
});

app.get('/report/:id/html', authMiddleware, async (req, res) => {
  res.redirect(`${PYTHON}/api/report/${req.params.id}/html`);
});

// Scheduler Routes
app.post('/api/schedule', authMiddleware, async (req, res) => {
  try {
    const response = await axios.post(`${PYTHON}/api/schedule`, req.body);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/schedules/:user_id', authMiddleware, async (req, res) => {
  try {
    const response = await axios.get(`${PYTHON}/api/schedules/${req.params.user_id}`);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/scan/:id/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  axios({
    method: 'get',
    url: `${PYTHON}/api/scan/${req.params.id}/stream`,
    responseType: 'stream'
  }).then(response => {
    response.data.pipe(res);
    req.on('close', () => {
      response.data.destroy();
    });
  }).catch(err => {
    res.end();
  });
});

app.post('/check-ip', authMiddleware, async (req, res) => {
  try {
    const response = await axios.post(`${PYTHON}/api/check-ip`, req.body);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.response?.data?.detail || err.message });
  }
});

// Connect to MongoDB
const connectDB = async () => {
  if (mongoose.connection.readyState >= 1) return;
  const uri = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/websecurex';
  try {
    await mongoose.connect(uri);
    console.log('✅ MongoDB connected');
  } catch (err) {
    console.error('DB connection error:', err);
  }
};

// Middleware to ensure DB is connected before processing requests
app.use(async (req, res, next) => {
  await connectDB();
  next();
});

// Start local server if not running on Vercel
if (!process.env.VERCEL) {
  connectDB().then(() => {
    const port = process.env.NODE_PORT || process.env.PORT || 3000;
    app.listen(port, () => console.log(`🚀 WebSecureX running → http://localhost:${port}`));
  });
}

module.exports = app;

