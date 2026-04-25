import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入原始页面并调用 render()
try:
    if 'original_pages' == 'app_pages':
        from app_pages.data_importer import render
    else:
        from original_pages.data_importer import render
    
    render()
except Exception as e:
    st.error(f"页面加载失败: {e}")
    import traceback
    st.error(traceback.format_exc())
