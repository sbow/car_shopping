require('dotenv').config({ path: '../../.env' });
const express = require('express');
const axios = require('axios');
const path = require('path');

const app = express();
const PORT = process.env.DASHBOARD_PORT || 3000;
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));

async function api(endpoint) {
  const res = await axios.get(`${API_BASE}${endpoint}`);
  return res.data;
}

app.get('/', async (req, res) => {
  try {
    const watchlist = await api('/api/watchlist');
    res.render('index', { watchlist });
  } catch (e) {
    res.render('error', { message: e.message });
  }
});

app.get('/listings', async (req, res) => {
  try {
    const { make, model, year_min, year_max, max_price, sort_by, sort_dir } = req.query;
    const params = new URLSearchParams(
      Object.fromEntries(
        Object.entries({ make, model, year_min, year_max, max_price, sort_by, sort_dir })
          .filter(([, v]) => v)
      )
    );
    const [listings, options] = await Promise.all([
      api(`/api/listings?${params}`),
      api('/api/listings/options'),
    ]);
    res.render('listings', { listings, query: req.query, options });
  } catch (e) {
    res.render('error', { message: e.message });
  }
});

app.get('/depreciation', async (req, res) => {
  try {
    const data = await api('/api/depreciation');
    res.render('depreciation', { data });
  } catch (e) {
    res.render('error', { message: e.message });
  }
});

app.get('/alternatives', async (req, res) => {
  try {
    const data = await api('/api/alternatives');
    res.render('alternatives', { data });
  } catch (e) {
    res.render('error', { message: e.message });
  }
});

app.get('/cost', async (req, res) => {
  try {
    const data = await api('/api/cost_of_ownership');
    res.render('cost_of_ownership', { data });
  } catch (e) {
    res.render('error', { message: e.message });
  }
});

app.listen(PORT, () => {
  console.log(`Dashboard running at http://localhost:${PORT}`);
});
