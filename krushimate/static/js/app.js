
// Enhanced app.js with profile integration & user sync

const LS = {
  getCurrent(){ return JSON.parse(localStorage.getItem('user')||localStorage.getItem('current')||'null') },
  setCurrent(user){ localStorage.setItem('user', JSON.stringify(user)) },
  getProfile(){ return JSON.parse(localStorage.getItem('krushimateProfile')||'null') },
  setProfile(profile){ localStorage.setItem('krushimateProfile', JSON.stringify(profile)) },
  getFarmers(){ return JSON.parse(localStorage.getItem('farmers')||'[]') },
  setFarmers(arr){ localStorage.setItem('farmers', JSON.stringify(arr)) }
};

// Register/Login (existing)
function registerUser(e){
  e.preventDefault();
  const data = {
    first_name: document.getElementById('name').value.trim(),
    phone: document.getElementById('phone').value.trim(),
    password: document.getElementById('password').value
  };
  if(!data.first_name||!data.phone||!data.password){ showToast('Please fill all fields', 'error'); return; }
  
  fetch('/api/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  }).then(res => res.json()).then(result => {
    if(result.status === 'ok'){
      LS.setCurrent({name: data.first_name, phone: data.phone});
      showToast('Registered!');
      window.location = '/dashboard';
    } else {
      showToast(result.message, 'error');
    }
  });
}

function loginUser(e){
  e.preventDefault();
  const data = {
    username: document.getElementById('login_phone').value.trim(),
    password: document.getElementById('login_password').value
  };
  
  fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  }).then(res => res.json()).then(result => {
    if(result.status === 'ok'){
      LS.setCurrent(result.user);
      showToast('Welcome back!');
      window.location = '/dashboard';
    } else {
      showToast(result.message, 'error');
    }
  });
}

// Enhanced Dashboard load
function loadDashboard(){
  const user = LS.getCurrent();
  if(!user){ window.location='/login'; return; }
  
  const welcomeEl = document.getElementById('welcome');
  if(welcomeEl) welcomeEl.textContent = `Welcome, ${user.name || user.first_name || 'Farmer'}!`;
  updateDashboardStats();
}

async function updateDashboardStats(){
  const user = LS.getCurrent();
  if (!user || !user.id) return;
  
  try {
    const response = await fetch('/api/user_crops');
    const crops = await response.json();
    const totalCropsEl = document.getElementById('total-crops');
    if(totalCropsEl){
      totalCropsEl.textContent = crops.length || 0;
    }
  } catch {
    // Fallback to 0
  }
}

// Profile-specific functions
function loadProfile() {
  const user = LS.getCurrent();
  const profile = LS.getProfile() || {};
  
  // Use exact username as profile name
  const profileName = document.getElementById('profileName');
  if(profileName) profileName.textContent = user.username || user.name || user.first_name || 'Farmer';
  
  const profilePhone = document.getElementById('profilePhone');
  if(profilePhone) profilePhone.textContent = user.phone || profile.phone || '+91 XXXXX XXXXX';
  
  // Stats
  document.getElementById('totalAcres').textContent = profile.farm?.acres || 25;
  document.getElementById('cropsCount').textContent = (profile.crops || []).length;
  document.getElementById('totalOrders').textContent = profile.orders || 12;
  
  // Form fills
  document.getElementById('editName').value = user.first_name || user.name || '';
  document.getElementById('editPhone').value = user.phone || '';
  document.getElementById('editEmail').value = user.email || '';
  document.getElementById('farmName').value = profile.farm?.name || '';
  document.getElementById('totalArea').value = profile.farm?.acres || 25;
  document.getElementById('soilType').value = profile.farm?.soil || 'Loamy';
  document.getElementById('irrigation').value = profile.farm?.irrigation || 'Drip';
  
  renderCrops();
  renderYieldChart();
}

// Save profile data
function saveProfile() {
  LS.setProfile(profileData);
  showToast('Profile saved!', 'success');
  loadProfile();
}

// Tab switching (data-tab based)
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('show'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById(btn.dataset.tab).classList.add('show');
      btn.classList.add('active');
    });
  });
  
  // Profile page specific
  if (document.getElementById('profileName')) loadProfile();
  
  // Forms
  const profileForm = document.getElementById('profileForm');
  if (profileForm) {
    profileForm.addEventListener('submit', e => {
      e.preventDefault();
      profileData.name = document.getElementById('editName').value;
      profileData.phone = document.getElementById('editPhone').value;
      profileData.email = document.getElementById('editEmail').value;
      saveProfile();
    });
  }
  
  // Dashboard & crop sync
  if(document.getElementById('welcome')) loadDashboard();
  
  // Listen for crop updates globally
  window.addEventListener('cropsUpdated', updateDashboardStats);
  
  const regForm = document.getElementById('registerForm');
  if(regForm) regForm.addEventListener('submit', registerUser);
  const loginForm = document.getElementById('loginForm');
  if(loginForm) loginForm.addEventListener('submit', loginUser);
});

function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  if (toast) {
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    setTimeout(() => toast.classList.remove('show'), 3000);
  }
}

// Crop/Yeild functions (existing)
let profileData = JSON.parse(localStorage.getItem('krushimateProfile')) || {
  farm: { acres: 25, soil: 'Loamy' },
  crops: []
};

function renderCrops() {
  // Implementation as before
}

function renderYieldChart() {
  // Implementation as before
}

// ... rest of crop management functions

