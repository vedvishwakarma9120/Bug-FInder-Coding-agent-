import os
import sys
import json
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv
from groq import Groq

from tools import ToolExecutor
from agent import get_best_model

load_dotenv()

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Repair & Verifier</title>
    <style>
        :root {
            --bg: #000000;
            --surface: #0c0c0c;
            --surface-subtle: #141414;
            --border: #262626;
            --border-hover: #404040;
            --text-main: #ffffff;
            --text-dim: #888888;
            --text-muted: #555555;
            --btn-white: #ffffff;
            --btn-white-text: #000000;
            --font-mono: "JetBrains Mono", Consolas, "Courier New", monospace;
            --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: var(--font-sans);
            background: var(--bg);
            color: var(--text-main);
            padding: 24px;
            min-height: 100vh;
            line-height: 1.5;
        }

        /* Top Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 18px;
            margin-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }
        .header-title {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .header-sub {
            font-size: 13px;
            color: var(--text-dim);
            margin-top: 3px;
        }
        .badge {
            font-family: var(--font-mono);
            font-size: 11px;
            padding: 4px 10px;
            border-radius: 4px;
            border: 1px solid var(--border);
            background: var(--surface);
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .badge-active {
            border-color: #ffffff;
            color: #ffffff;
        }
        .badge-success {
            border-color: #ffffff;
            background: #ffffff;
            color: #000000;
            font-weight: 700;
        }

        /* 2-Column Code Windows */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Form elements */
        textarea, input, select {
            width: 100%;
            background: #050505;
            color: #f0f0f0;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 10px 12px;
            font-family: var(--font-mono);
            font-size: 13px;
            outline: none;
            transition: border-color 0.15s;
        }
        textarea:focus, input:focus, select:focus {
            border-color: #777777;
        }
        textarea.code-box {
            height: 320px;
            white-space: pre;
            overflow-x: auto;
            line-height: 1.5;
            tab-size: 4;
        }
        textarea[readonly] {
            color: #888888;
            background: #080808;
        }

        /* Buttons */
        .btn-row {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        .btn {
            background: var(--btn-white);
            color: var(--btn-white-text);
            border: 1px solid var(--btn-white);
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s;
            font-family: var(--font-sans);
        }
        .btn:hover {
            background: #e0e0e0;
            border-color: #e0e0e0;
        }
        .btn:disabled {
            opacity: 0.35;
            cursor: not-allowed;
        }
        .btn-outline {
            background: transparent;
            color: var(--text-main);
            border: 1px solid var(--border-hover);
        }
        .btn-outline:hover {
            border-color: #ffffff;
            background: #111111;
        }
        .btn-sm {
            padding: 5px 10px;
            font-size: 12px;
        }
        .btn-accept {
            background: #ffffff;
            color: #000000;
            border: 1px solid #ffffff;
        }
        .btn-accept:hover {
            background: #e0e0e0;
        }
        .btn-decline {
            background: transparent;
            color: var(--text-dim);
            border: 1px solid var(--border);
        }
        .btn-decline:hover {
            border-color: #777777;
            color: #ffffff;
        }

        /* Line by line review section */
        #analysis-section {
            display: none;
            flex-direction: column;
            gap: 16px;
            margin-bottom: 24px;
        }
        .section-header {
            font-size: 15px;
            font-weight: 700;
            letter-spacing: -0.3px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }
        .issue-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            transition: all 0.2s ease;
        }
        .issue-card.accepted {
            border-color: #ffffff;
            background: #111111;
        }
        .issue-card.declined {
            border-color: #333333;
            opacity: 0.65;
        }
        .issue-row {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .field-title {
            font-size: 13px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.2px;
        }
        .field-line-val {
            font-family: var(--font-mono);
            font-size: 13px;
            font-weight: 600;
            color: #ffffff;
            background: #181818;
            border: 1px solid var(--border);
            padding: 4px 10px;
            border-radius: 4px;
            display: inline-block;
            width: fit-content;
        }
        .field-reason-val {
            font-size: 13px;
            color: #cccccc;
            background: #080808;
            border: 1px solid var(--border);
            padding: 8px 12px;
            border-radius: 4px;
            line-height: 1.5;
        }
        .field-changement-box {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .issue-actions-row {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            padding-top: 8px;
            border-top: 1px solid var(--border);
        }
        .btn-decision-accept {
            background: transparent;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 6px 16px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .btn-decision-accept:hover {
            border-color: #ffffff;
            background: #222222;
        }
        .btn-decision-accept.active {
            background: #ffffff;
            color: #000000;
            border-color: #ffffff;
            font-weight: 700;
        }
        .btn-decision-decline {
            background: transparent;
            color: var(--text-dim);
            border: 1px solid var(--border);
            padding: 6px 16px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .btn-decision-decline:hover {
            border-color: #777777;
            color: #ffffff;
            background: #181818;
        }
        .btn-decision-decline.active {
            background: #242424;
            color: #ffffff;
            border-color: #666666;
            font-weight: 700;
        }

        /* Line diff preview */
        .diff-box {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            font-family: var(--font-mono);
            font-size: 12px;
        }
        .diff-pane {
            background: #050505;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 8px 12px;
            overflow-x: auto;
        }
        .diff-label {
            font-size: 11px;
            font-weight: 700;
            color: var(--text-dim);
            text-transform: uppercase;
            margin-bottom: 6px;
            padding-bottom: 4px;
            border-bottom: 1px solid var(--border);
        }
        .diff-old-text {
            color: #aaaaaa;
            text-decoration: line-through;
            white-space: pre-wrap;
        }
        .diff-new-text {
            color: #ffffff;
            font-weight: 600;
            white-space: pre-wrap;
        }

        /* Terminal Output Console */
        .terminal-box {
            background: #050505;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 12px;
            font-family: var(--font-mono);
            font-size: 12px;
            color: #dddddd;
            min-height: 100px;
            max-height: 220px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }

        /* Satisfaction Card */
        #satisfaction-box {
            display: none;
            background: #111111;
            border: 1px solid #ffffff;
            border-radius: 6px;
            padding: 16px;
            flex-direction: column;
            gap: 12px;
            margin-top: 14px;
        }
    </style>
</head>
<body>
    <!-- Top Header -->
    <div class="header">
        <div>
            <div class="header-title">
                <span>[ // ]</span> CODE REPAIR & VERIFIER STUDIO
            </div>
            <div class="header-sub">
                Full-code AI analysis &bull; Line-by-line interactive decision (Accept/Decline) &bull; Automated compiler verification &bull; Output window gate
            </div>
        </div>
        <div class="badge badge-active" id="model-tag">Groq LLM Engine</div>
    </div>

    <!-- 2 Code Windows (Side by Side) -->
    <div class="grid-2">
        <!-- Left: Input Code -->
        <div class="card">
            <div class="card-header">
                <div class="card-title">1. Your Input Code</div>
                <select id="lang" style="width: auto; padding: 4px 8px; font-size: 12px;" onchange="onLangChange()">
                    <option value="code.cpp">C++ (code.cpp)</option>
                    <option value="code.py">Python (code.py)</option>
                    <option value="code.js">JavaScript (code.js)</option>
                    <option value="code.txt">Plain Text (code.txt)</option>
                </select>
            </div>
            <textarea id="input-code" class="code-box" placeholder="// Paste your code here..."></textarea>

            <div style="font-size: 12px; color: var(--text-dim);">Optional: Add specific bug notes (or leave blank for full auto-analysis):</div>
            <input type="text" id="bug-desc" placeholder="e.g. Expected answer is 10, or fix compiler error" value="">

            <div class="btn-row">
                <button class="btn" id="analyze-btn" onclick="analyzeFullCode()">🔍 Analyze Full Code (AI)</button>
                <button class="btn btn-outline" id="quick-test-btn" onclick="testRawInput()">▶ Test Input with Compiler</button>
            </div>
        </div>

        <!-- Right: Final Output Code (Protected until user is satisfied & compiler passes) -->
        <div class="card">
            <div class="card-header">
                <div class="card-title">2. Final Verified Code (Output Window)</div>
                <span class="badge" id="output-gate-badge">🔒 Locked</span>
            </div>
            <textarea id="output-code" class="code-box" placeholder="Output window is locked.&#10;&#10;Workflow:&#10;1. Click 'Analyze Full Code' to inspect the entire code.&#10;2. Review each line error and choose Accept or Decline.&#10;3. Run the automated compiler test.&#10;4. Once you are satisfied with the verified code, click 'Approve & Send to Output Window'." readonly></textarea>

            <div style="font-size: 12px; color: var(--text-dim);" id="output-status-text">
                Status: Awaiting full analysis, line reviews, and compiler verification.
            </div>

            <div class="btn-row">
                <button class="btn btn-outline" id="copy-btn" onclick="copyFinalCode()" disabled>📋 Copy Final Code</button>
            </div>
        </div>
    </div>

    <!-- AI Full Code Analysis & Line-by-Line Changes Section -->
    <div id="analysis-section">
        <div class="section-header">
            <div>
                <span>3. Entire Code Analysis & Line-by-Line Decisions</span>
                <span style="font-size: 12px; font-weight: normal; color: var(--text-dim); margin-left: 10px;" id="issues-count-text"></span>
            </div>
            <span class="badge" id="staging-status-badge">0 Changes Applied</span>
        </div>

        <!-- Overall AI diagnosis summary -->
        <div id="overall-analysis-container" style="background: var(--surface-subtle); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; display: none;">
            <div style="font-size: 11px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Whole-Code Analysis Summary:</div>
            <div id="overall-analysis-text" style="font-size: 13px; color: #ffffff; white-space: pre-wrap;"></div>
        </div>

        <!-- Interactive Line Changes List -->
        <div id="issues-list" style="display: flex; flex-direction: column; gap: 14px;"></div>

        <!-- Compiler Verification Card -->
        <div class="card" style="margin-top: 10px;">
            <div class="card-header">
                <div class="card-title">4. Automated Compiler & Test Suite Verification</div>
                <span class="badge" id="test-verdict-badge">Not Run Yet</span>
            </div>

            <div style="font-size: 13px; color: var(--text-dim);">
                Click below to compile and execute your code with all accepted line changes:
            </div>

            <div class="btn-row">
                <button class="btn" id="run-verify-btn" onclick="verifyStagedCode()">⚡ Run Automated Compiler Verification</button>
            </div>

            <div class="terminal-box" id="compiler-console">Compiler output will appear here after clicking verify...</div>

            <!-- Satisfaction Box (Enabled only after compiler verifies) -->
            <div id="satisfaction-box">
                <div style="font-size: 14px; font-weight: 700; color: #ffffff;">
                    ✅ Compiler Test Passed! Are you satisfied with this code?
                </div>
                <div style="font-size: 13px; color: #cccccc;">
                    All accepted line changes have been compiled and verified without boilerplate errors. If you are satisfied, approve the code to send it into the Final Output Window.
                </div>
                <div class="btn-row">
                    <button class="btn btn-accept" onclick="approveAndFinalize()">✓ I Am Satisfied — Send to Final Output Window</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let originalCode = "";
        let detectedIssues = [];
        let stagedCode = "";
        let compilerPassed = false;

        window.addEventListener('DOMContentLoaded', () => {
            loadInitialFile();
        });

        async function loadInitialFile() {
            const lang = document.getElementById('lang').value;
            try {
                const res = await fetch('/api/load_current?filename=' + encodeURIComponent(lang));
                const data = await res.json();
                if (data.code) {
                    document.getElementById('input-code').value = data.code;
                }
            } catch (e) {
                // Ignore load error
            }
        }

        async function onLangChange() {
            await loadInitialFile();
        }

        async function testRawInput() {
            const code = document.getElementById('input-code').value;
            const filename = document.getElementById('lang').value;
            if (!code.trim()) {
                alert('Please enter some code first.');
                return;
            }

            const btn = document.getElementById('quick-test-btn');
            btn.disabled = true;
            btn.innerText = '⏳ Compiling...';

            try {
                const res = await fetch('/api/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, filename })
                });
                const data = await res.json();
                alert((data.success ? '✅ COMPILER SUCCESS' : '❌ COMPILER FAILED') + '\\n\\nCommand: ' + data.command + '\\n\\n' + data.output);
            } catch (err) {
                alert('Error running compiler: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerText = '▶ Test Input with Compiler';
            }
        }

        async function analyzeFullCode() {
            const code = document.getElementById('input-code').value;
            const filename = document.getElementById('lang').value;
            const bug = document.getElementById('bug-desc').value.trim();

            if (!code.trim()) {
                alert('Please paste or write your code first!');
                return;
            }

            originalCode = code;
            compilerPassed = false;
            document.getElementById('satisfaction-box').style.display = 'none';

            const analyzeBtn = document.getElementById('analyze-btn');
            analyzeBtn.disabled = true;
            analyzeBtn.innerText = '⏳ AI Analyzing Entire Code...';

            // Show section immediately with loading state
            document.getElementById('analysis-section').style.display = 'flex';
            document.getElementById('overall-analysis-container').style.display = 'none';
            document.getElementById('issues-list').innerHTML = '<div style="color: var(--text-dim); font-size: 13px; padding: 14px; background: #080808; border-radius: 4px; border: 1px solid var(--border);">⏳ AI is analyzing the entire code line by line... Please wait.</div>';
            document.getElementById('issues-count-text').innerText = '(Analyzing...)';
            document.getElementById('analysis-section').scrollIntoView({ behavior: 'smooth' });

            try {
                const res = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, filename, bug })
                });
                const data = await res.json();

                if (data.error) {
                    alert('Analysis error: ' + data.error);
                    document.getElementById('issues-list').innerHTML = `<div style="color: #ff6666; font-size: 13px; padding: 12px; background: #140808; border-radius: 4px;">${escapeHtml(data.error)}</div>`;
                    return;
                }

                detectedIssues = (data.issues || []).map(iss => ({
                    ...iss,
                    accepted: null // null: pending, true: yes, false: no
                }));

                // Update section display
                if (data.overall_analysis) {
                    document.getElementById('overall-analysis-container').style.display = 'block';
                    document.getElementById('overall-analysis-text').innerText = data.overall_analysis;
                } else {
                    document.getElementById('overall-analysis-container').style.display = 'none';
                }
                document.getElementById('issues-count-text').innerText = '(' + detectedIssues.length + ' problematic line/sections identified)';

                renderIssuesList();
                recomputeStagedCode();
            } catch (err) {
                alert('Connection error: ' + err.message);
                document.getElementById('issues-list').innerHTML = `<div style="color: #ff6666; font-size: 13px; padding: 12px; background: #140808; border-radius: 4px;">Error: ${escapeHtml(err.message)}</div>`;
            } finally {
                analyzeBtn.disabled = false;
                analyzeBtn.innerText = '🔍 Analyze Full Code (AI)';
            }
        }

        function renderIssuesList() {
            const container = document.getElementById('issues-list');
            container.innerHTML = '';

            if (detectedIssues.length === 0) {
                container.innerHTML = '<div style="color: var(--text-dim); font-size: 13px; padding: 12px; background: #080808; border-radius: 4px;">No syntax or logic issues detected across the code! You can proceed to test with compiler.</div>';
                return;
            }

            detectedIssues.forEach((issue, index) => {
                const card = document.createElement('div');
                card.className = 'issue-card' + (issue.accepted === true ? ' accepted' : (issue.accepted === false ? ' declined' : ''));

                const lineLabel = (issue.start_line === issue.end_line)
                    ? `Line ${issue.start_line}`
                    : `Lines ${issue.start_line} - ${issue.end_line}`;

                let statusBadge = '<span class="badge">Pending</span>';
                if (issue.accepted === true) {
                    statusBadge = '<span class="badge badge-success">✓ Accepted</span>';
                } else if (issue.accepted === false) {
                    statusBadge = '<span class="badge" style="border-color: #555555; color: #aaaaaa;">✕ Declined</span>';
                }

                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 6px; border-bottom: 1px solid var(--border);">
                        <span style="font-size: 13px; font-weight: 700; color: #ffffff;">Issue #${index + 1}: ${escapeHtml(issue.title || 'Error')}</span>
                        <div>${statusBadge}</div>
                    </div>

                    <div class="issue-row">
                        <span class="field-title">Error line :</span>
                        <span class="field-line-val">${lineLabel}</span>
                    </div>

                    <div class="issue-row">
                        <span class="field-title">Error reason :</span>
                        <div class="field-reason-val">${escapeHtml(issue.explanation || issue.title || 'Problematic line detected')}</div>
                    </div>

                    <div class="issue-row">
                        <span class="field-title">changement :</span>
                        <div class="field-changement-box">
                            <div class="diff-box">
                                <div class="diff-pane">
                                    <div class="diff-label">Current Code (${lineLabel})</div>
                                    <div class="diff-old-text">${escapeHtml(issue.old_code || '')}</div>
                                </div>
                                <div class="diff-pane">
                                    <div class="diff-label">Proposed Fix</div>
                                    <div class="diff-new-text">${escapeHtml(issue.new_code || '')}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="issue-actions-row">
                        <div class="btn-row">
                            <button class="btn btn-sm ${issue.accepted === true ? 'btn-decision-accept active' : 'btn-decision-accept'}" onclick="setIssueDecision(${index}, true)">
                                ✓ Accept
                            </button>
                            <button class="btn btn-sm ${issue.accepted === false ? 'btn-decision-decline active' : 'btn-decision-decline'}" onclick="setIssueDecision(${index}, false)">
                                ✕ Decline
                            </button>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        function setIssueDecision(index, decision) {
            if (detectedIssues[index].accepted === decision) {
                detectedIssues[index].accepted = null;
            } else {
                detectedIssues[index].accepted = decision;
            }
            renderIssuesList();
            recomputeStagedCode();
            // Invalidate previous compiler pass until re-verified
            compilerPassed = false;
            document.getElementById('satisfaction-box').style.display = 'none';
        }

        function recomputeStagedCode() {
            let lines = originalCode.split('\\n');

            // Apply all accepted fixes in descending order of start_line to avoid index shift
            const accepted = detectedIssues
                .filter(iss => iss.accepted === true)
                .sort((a, b) => b.start_line - a.start_line);

            for (const item of accepted) {
                const s = Math.max(0, parseInt(item.start_line) - 1);
                const e = Math.min(lines.length, parseInt(item.end_line));
                const count = Math.max(1, e - s);
                const newSlice = (item.new_code || '').split('\\n');
                lines.splice(s, count, ...newSlice);
            }

            stagedCode = lines.join('\\n');

            const acceptedCount = detectedIssues.filter(iss => iss.accepted === true).length;
            const totalCount = detectedIssues.length;
            document.getElementById('staging-status-badge').innerText = `${acceptedCount} of ${totalCount} Changes Accepted`;
        }

        async function verifyStagedCode() {
            const filename = document.getElementById('lang').value;
            const codeToTest = stagedCode || originalCode;
            const consoleEl = document.getElementById('compiler-console');
            const verdictBadge = document.getElementById('test-verdict-badge');
            const verifyBtn = document.getElementById('run-verify-btn');

            verifyBtn.disabled = true;
            verifyBtn.innerText = '⏳ Compiling & Testing...';
            consoleEl.innerText = 'Running automated compiler verification on staged code...\\n';

            try {
                const res = await fetch('/api/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: codeToTest, filename })
                });
                const data = await res.json();

                if (data.success) {
                    compilerPassed = true;
                    verdictBadge.className = 'badge badge-success';
                    verdictBadge.innerText = '✅ VERIFICATION PASSED';
                    consoleEl.innerText = '==> COMPILER VERIFICATION PASSED\\nCommand: ' + data.command + '\\n\\n' + (data.output || '(Execution completed with code 0)');
                    document.getElementById('satisfaction-box').style.display = 'flex';
                } else {
                    compilerPassed = false;
                    verdictBadge.className = 'badge';
                    verdictBadge.innerText = '❌ VERIFICATION FAILED';
                    consoleEl.innerText = '==> COMPILATION / RUNTIME FAILED\\nCommand: ' + data.command + '\\n\\n' + data.output;
                    document.getElementById('satisfaction-box').style.display = 'none';
                }
            } catch (err) {
                consoleEl.innerText = 'Error running verification: ' + err.message;
                verdictBadge.innerText = 'Error';
            } finally {
                verifyBtn.disabled = false;
                verifyBtn.innerText = '⚡ Run Automated Compiler Verification';
            }
        }

        async function approveAndFinalize() {
            const filename = document.getElementById('lang').value;
            const finalCode = stagedCode || originalCode;

            try {
                const res = await fetch('/api/finalize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: finalCode, filename })
                });
                const data = await res.json();

                // Put code in Output Window
                const outBox = document.getElementById('output-code');
                outBox.value = finalCode;
                outBox.removeAttribute('readonly');

                document.getElementById('output-gate-badge').className = 'badge badge-success';
                document.getElementById('output-gate-badge').innerText = '✅ Final & Verified';
                document.getElementById('output-status-text').innerHTML = '<strong style="color: #ffffff;">✅ You approved this code!</strong> Compiler verified with zero errors.';
                document.getElementById('copy-btn').disabled = false;

                // Scroll to top output window
                outBox.scrollIntoView({ behavior: 'smooth' });
                alert('🎉 Done! Verified code is now placed in the Output Window.');
            } catch (err) {
                alert('Error finalizing: ' + err.message);
            }
        }

        function copyFinalCode() {
            const out = document.getElementById('output-code');
            if (!out.value) return;
            out.select();
            navigator.clipboard.writeText(out.value);
            alert('✅ Final verified code copied to clipboard!');
        }

        function escapeHtml(text) {
            return (text || '')
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }
    </script>
</body>
</html>
"""

def parse_groq_json(raw_text: str) -> dict:
    """Robust JSON parser that strips markdown code fences if present."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return json.loads(text)

class AgentHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path.startswith("/api/load_current"):
            query = self.path.split("?")[-1] if "?" in self.path else ""
            filename = "code.cpp"
            for q in query.split("&"):
                if q.startswith("filename="):
                    filename = q.split("=")[-1]
            project_dir = Path("bugged_code").resolve()
            target_file = project_dir / filename
            code = target_file.read_text(encoding="utf-8", errors="ignore") if target_file.is_file() else ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"filename": filename, "code": code}).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(body) if body else {}

        project_dir = Path("bugged_code").resolve()
        project_dir.mkdir(parents=True, exist_ok=True)
        tool_executor = ToolExecutor(project_dir)

        if self.path == "/api/test":
            code = data.get("code", "")
            filename = data.get("filename", "code.cpp")
            target_file = project_dir / filename
            target_file.write_text(code, encoding="utf-8")

            test_res = tool_executor.run_tests(target_file=filename)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(test_res).encode("utf-8"))

        elif self.path == "/api/analyze":
            code = data.get("code", "")
            bug = data.get("bug", "")
            filename = data.get("filename", "code.cpp")

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "GROQ_API_KEY not configured in environment or .env."}).encode("utf-8"))
                return

            client = Groq(api_key=api_key)
            model = get_best_model(client)

            lines = code.splitlines()
            numbered_code = "\n".join(f"{i+1:3d} | {l}" for i, l in enumerate(lines))

            prompt = f"""You are an elite static analyzer, compiler expert, and bug fixing agent.
Analyze the user's ENTIRE code thoroughly from line 1 to the end.
DO NOT STOP at the first error! Inspect every single line.

CRITICAL RULES:
1. Detect ALL bugs, including:
   - Missing headers or missing boilerplate (e.g. #include <iostream>, using namespace std; in C++)
   - Syntax errors
   - Logic bugs and operator errors (e.g. subtraction instead of addition, wrong conditionals)
   - Undefined behaviors (e.g. multiple unsequenced modifications like x++ == ++x)
   - Out of bound memory accesses
2. For EVERY issue found:
   - start_line & end_line (1-indexed)
   - title: Short description
   - explanation: Clear explanation of why this line is wrong
   - old_code: Exact code line(s) from original input
   - new_code: Exact suggested replacement line(s) that fix only those specific lines
3. If the code is already completely correct, return "issues": [] with an explanation in "overall_analysis".

Target File: {filename}
User Bug Description: {bug or 'No additional notes provided'}

Code with line numbers:
{numbered_code}

Raw Code:
```{code}```

Return ONLY a valid JSON object matching this schema:
{{
  "overall_analysis": "Comprehensive summary of all issues in the entire code",
  "issues": [
    {{
      "id": 1,
      "start_line": 1,
      "end_line": 1,
      "title": "Title of issue",
      "explanation": "Why this line is wrong",
      "old_code": "exact lines from original code",
      "new_code": "exact proposed replacement code"
    }}
  ]
}}
"""
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a professional code analyzer. Output only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                raw_json = resp.choices[0].message.content
                analysis_data = parse_groq_json(raw_json)
            except Exception as e:
                analysis_data = {
                    "overall_analysis": f"Analysis error: {e}",
                    "issues": []
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(analysis_data).encode("utf-8"))

        elif self.path == "/api/finalize":
            filename = data.get("filename", "code.cpp")
            final_code = data.get("code", "")
            target_file = project_dir / filename
            target_file.write_text(final_code, encoding="utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "finalized", "filename": filename}).encode("utf-8"))

        else:
            self.send_error(404)

def main():
    port = 5000
    server = HTTPServer(("localhost", port), AgentHandler)
    url = f"http://localhost:{port}"
    print("=" * 65)
    print(f"🚀 AI Code Repair & Verifier running at: {url}")
    print("   • Clean Black & White Monochrome UI")
    print("   • Full-code AI analysis (inspects entire code, never stops at 1 error)")
    print("   • Interactive Accept/Decline approval on every problematic line")
    print("   • Automated compiler verification (with smart boilerplate handling)")
    print("   • Output window locked until user is satisfied & tests pass")
    print("   • Press Ctrl + C to stop the server.")
    print("=" * 65)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")

if __name__ == "__main__":
    main()
