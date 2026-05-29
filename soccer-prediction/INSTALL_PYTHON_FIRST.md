# ⚠️ PYTHON IS NOT INSTALLED ON YOUR SYSTEM

## The Issue
The error `'python' is not recognized` means Python is **not installed** or **not in your system PATH**.

## 🔧 SOLUTION: Install Python (Takes 5 Minutes)

### Step-by-Step Installation:

#### 1. Download Python
Go to: **https://www.python.org/downloads/**

Click the big yellow button: **"Download Python 3.11.x"**

#### 2. Run the Installer
- **IMPORTANT**: ✅ Check the box "Add Python to PATH" at the bottom
- Click "Install Now"
- Wait 2-3 minutes

#### 3. Verify Installation
Open a **NEW Command Prompt** (important - close old ones) and type:
```cmd
python --version
```

You should see: `Python 3.11.x`

#### 4. Install Packages
```cmd
cd C:\Users\FX\soccer_prediction_bot
python -m pip install requests pandas numpy
```

#### 5. Test Setup
```cmd
python test_setup.py
```

---

## 🎯 Alternative Methods

### Method 1: Microsoft Store (Easiest)
1. Open Microsoft Store
2. Search "Python 3.11"
3. Click "Get"
4. Wait for installation
5. Open new Command Prompt and type `python --version`

### Method 2: Chocolatey (If you have it)
```cmd
choco install python
```

### Method 3: Winget (Windows 11)
```cmd
winget install Python.Python.3.11
```

---

## 🐍 After Installing Python

Run these commands in order:

```cmd
# 1. Verify Python is installed
python --version

# 2. Upgrade pip
python -m pip install --upgrade pip

# 3. Install essential packages
python -m pip install requests pandas numpy

# 4. Test your setup
cd C:\Users\FX\soccer_prediction_bot
python test_setup.py

# 5. Install all dependencies (optional, takes 10 min)
python -m pip install -r requirements.txt

# 6. Run demo
python demo.py
```

---

## ✅ Quick Checklist

- [ ] Download Python from python.org
- [ ] Run installer with "Add to PATH" checked
- [ ] Close all Command Prompts
- [ ] Open NEW Command Prompt
- [ ] Type `python --version` to verify
- [ ] Install packages: `python -m pip install requests pandas numpy`
- [ ] Test: `python test_setup.py`

---

## 🎥 Video Tutorial

If you're stuck, watch this 3-minute tutorial:
**"How to Install Python on Windows"**
https://www.youtube.com/results?search_query=install+python+windows+11

---

## 🆘 Still Having Issues?

### Issue: "python: command not found" after installation
**Solution**: 
1. Close ALL Command Prompt windows
2. Open a NEW Command Prompt
3. Try again

### Issue: Python installed but still not recognized
**Solution**: Add Python to PATH manually
1. Search "Environment Variables" in Windows
2. Click "Environment Variables"
3. Under "System Variables", find "Path"
4. Click "Edit"
5. Click "New"
6. Add: `C:\Users\FX\AppData\Local\Programs\Python\Python311`
7. Add: `C:\Users\FX\AppData\Local\Programs\Python\Python311\Scripts`
8. Click OK
9. Restart Command Prompt

### Issue: Don't have admin rights
**Solution**: Use portable Python:
1. Download: https://www.python.org/ftp/python/3.11.7/python-3.11.7-embed-amd64.zip
2. Extract to `C:\Users\FX\Python311`
3. Use full path: `C:\Users\FX\Python311\python.exe test_setup.py`

---

## 🚀 Once Python Is Installed

You can run the soccer prediction bot with:

```cmd
cd C:\Users\FX\soccer_prediction_bot

# Quick test (no API calls)
python demo.py

# Test APIs
python test_setup.py

# Full pipeline (requires data collection first)
python main.py --step train
```

---

## 📞 Need More Help?

1. **Python Installation Issues**: https://docs.python.org/3/using/windows.html
2. **Pip Issues**: Run `python -m ensurepip --upgrade`
3. **Permission Issues**: Run Command Prompt as Administrator

---

## 💡 Summary

**You need to install Python first!**

1. Go to: https://www.python.org/downloads/
2. Download and install (check "Add to PATH")
3. Verify: `python --version`
4. Install packages: `python -m pip install requests pandas numpy`
5. Test: `python test_setup.py`

**That's it!** After Python is installed, everything will work. 🎉

---

**Python Download Link**: https://www.python.org/downloads/
