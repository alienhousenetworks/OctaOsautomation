"""Embeddable JavaScript Widget Generator for OctaOS Customer Support & AI Live Chat."""

def get_widget_embed_js(default_api_base: str = "") -> str:
    """Returns standalone, zero-dependency vanilla JS widget code."""
    return f"""(function() {{
  if (window.__OctaSupportInitialized) return;
  window.__OctaSupportInitialized = true;

  // 1. Identify configuration
  const scriptTag = document.currentScript || document.querySelector('script[data-tenant-id]');
  const tenantId = scriptTag ? scriptTag.getAttribute('data-tenant-id') : (window.OctaSupportTenantId || '');
  const explicitApiBase = scriptTag ? scriptTag.getAttribute('data-api-base') : '';
  const apiBase = explicitApiBase || (scriptTag && scriptTag.src ? new URL(scriptTag.src).origin : '{default_api_base}' || window.location.origin);
  const apiPrefix = apiBase + '/api/v1/support';

  if (!tenantId) {{
    console.warn('[OctaOS Support] Missing data-tenant-id attribute on script tag.');
    return;
  }}

  // 2. Session ID Management
  let sessionId = localStorage.getItem('octaos_widget_session_' + tenantId);
  if (!sessionId) {{
    sessionId = 'sess_' + Math.random().toString(36).substring(2, 12) + '_' + Date.now();
    localStorage.setItem('octaos_widget_session_' + tenantId, sessionId);
  }}

  let widgetConfig = {{
    title: 'Customer Support',
    welcome_message: 'Hi there! How can we assist you today?',
    brand_color: '#2563eb',
    live_chat_available: false,
  }};

  let isOpen = false;
  let activeTab = 'chat'; // 'chat' | 'ticket'
  let ticketStatus = 'open'; // 'open' | 'pending_human' | 'human_handling' | 'resolved'
  let messages = [];
  let pollInterval = null;
  const renderedIds = {{}};
  const aiShown = {{}};

  // 3. Inject CSS Styles
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    #octaos-widget-root * {{
      box-sizing: border-box;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    #octaos-widget-root {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 999999;
    }}
    .octa-launcher-btn {{
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      box-shadow: 0 8px 24px rgba(37, 99, 235, 0.4), 0 2px 6px rgba(0,0,0,0.2);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      position: relative;
    }}
    .octa-launcher-btn:hover {{
      transform: scale(1.08) translateY(-2px);
      box-shadow: 0 12px 28px rgba(37, 99, 235, 0.5);
    }}
    .octa-launcher-btn:active {{
      transform: scale(0.95);
    }}
    .octa-online-badge {{
      position: absolute;
      top: 2px;
      right: 2px;
      width: 14px;
      height: 14px;
      background: #10b981;
      border: 2.5px solid #0f172a;
      border-radius: 50%;
    }}
    .octa-chat-window {{
      position: absolute;
      bottom: 74px;
      right: 0;
      width: 380px;
      height: 560px;
      max-height: calc(100vh - 100px);
      background: #0f172a;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 20px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      opacity: 0;
      pointer-events: none;
      transform: translateY(16px) scale(0.96);
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .octa-chat-window.octa-open {{
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0) scale(1);
    }}
    .octa-header {{
      background: #1e293b;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }}
    .octa-header-title {{
      font-weight: 700;
      font-size: 14px;
      color: #f8fafc;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .octa-header-status {{
      font-size: 11px;
      color: #94a3b8;
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .octa-status-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10b981;
    }}
    .octa-close-btn {{
      background: transparent;
      border: none;
      color: #94a3b8;
      cursor: pointer;
      font-size: 18px;
      padding: 4px 8px;
      border-radius: 6px;
      transition: background 0.2s;
    }}
    .octa-close-btn:hover {{
      background: rgba(255,255,255,0.1);
      color: #fff;
    }}
    .octa-tabs-bar {{
      display: flex;
      background: #111827;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      padding: 4px;
    }}
    .octa-tab-btn {{
      flex: 1;
      background: transparent;
      border: none;
      color: #94a3b8;
      font-size: 11px;
      font-weight: 600;
      padding: 6px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .octa-tab-btn.active {{
      background: #1e293b;
      color: #38bdf8;
    }}
    .octa-messages-wrap {{
      flex: 1;
      padding: 14px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: #0b1120;
    }}
    .octa-bubble {{
      max-width: 82%;
      padding: 10px 14px;
      border-radius: 14px;
      font-size: 12.5px;
      line-height: 1.45;
      word-break: break-word;
      animation: octaFadeIn 0.2s ease-out;
    }}
    @keyframes octaFadeIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .octa-bubble-customer {{
      align-self: flex-end;
      background: #2563eb;
      color: #ffffff;
      border-bottom-right-radius: 2px;
    }}
    .octa-bubble-agent {{
      align-self: flex-start;
      background: #1e293b;
      color: #e2e8f0;
      border: 1px solid rgba(255,255,255,0.08);
      border-bottom-left-radius: 2px;
    }}
    .octa-bubble-system {{
      align-self: center;
      background: rgba(30, 41, 59, 0.6);
      color: #94a3b8;
      font-size: 11px;
      padding: 6px 12px;
      border-radius: 20px;
      border: 1px dashed rgba(255,255,255,0.15);
      text-align: center;
      max-width: 90%;
    }}
    .octa-citations {{
      margin-top: 6px;
      padding-top: 6px;
      border-top: 1px solid rgba(255,255,255,0.1);
      font-size: 10px;
      color: #94a3b8;
    }}
    .octa-handoff-prompt {{
      background: #1e1b4b;
      border: 1px solid #4338ca;
      border-radius: 12px;
      padding: 10px 12px;
      margin-top: 4px;
      color: #c7d2fe;
      font-size: 11.5px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .octa-action-btn {{
      background: #4f46e5;
      color: white;
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
      align-self: flex-start;
    }}
    .octa-action-btn:hover {{
      background: #4338ca;
    }}
    .octa-input-wrap {{
      padding: 10px;
      background: #0f172a;
      border-top: 1px solid rgba(255,255,255,0.08);
      display: flex;
      gap: 8px;
    }}
    .octa-input {{
      flex: 1;
      background: #1e293b;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 10px;
      color: white;
      padding: 8px 12px;
      font-size: 12px;
      outline: none;
    }}
    .octa-input:focus {{
      border-color: #38bdf8;
    }}
    .octa-send-btn {{
      background: #2563eb;
      border: none;
      color: white;
      border-radius: 10px;
      width: 36px;
      height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background 0.2s;
    }}
    .octa-send-btn:hover {{
      background: #1d4ed8;
    }}
    .octa-ticket-form {{
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      overflow-y: auto;
      flex: 1;
    }}
    .octa-form-label {{
      font-size: 11px;
      font-weight: 600;
      color: #94a3b8;
      margin-bottom: 2px;
    }}
    .octa-form-input {{
      width: 100%;
      background: #1e293b;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      color: white;
      padding: 8px 10px;
      font-size: 12px;
      outline: none;
    }}
    .octa-form-input:focus {{
      border-color: #38bdf8;
    }}
    .octa-form-textarea {{
      width: 100%;
      background: #1e293b;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      color: white;
      padding: 8px 10px;
      font-size: 12px;
      min-height: 70px;
      resize: vertical;
      outline: none;
    }}
    .octa-form-submit {{
      background: #10b981;
      border: none;
      color: white;
      padding: 10px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      margin-top: 4px;
      transition: background 0.2s;
    }}
    .octa-form-submit:hover {{
      background: #059669;
    }}
    .octa-quick-chips {{
      display: flex;
      gap: 6px;
      padding: 6px 10px;
      background: #0f172a;
      overflow-x: auto;
      border-top: 1px solid rgba(255,255,255,0.04);
    }}
    .octa-chip {{
      background: #1e293b;
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 12px;
      color: #94a3b8;
      font-size: 10.5px;
      padding: 3px 8px;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;
    }}
    .octa-chip:hover {{
      background: #334155;
      color: #fff;
    }}
  `;
  document.head.appendChild(styleEl);

  // 4. Inject Widget HTML
  const rootEl = document.createElement('div');
  rootEl.id = 'octaos-widget-root';
  rootEl.innerHTML = `
    <div class="octa-chat-window" id="octa-window">
      <div class="octa-header">
        <div class="octa-header-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span id="octa-title">Customer Support</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <div class="octa-header-status" id="octa-status">
            <span class="octa-status-dot"></span> <span id="octa-status-text">AI Ready</span>
          </div>
          <button class="octa-close-btn" id="octa-close-btn" title="Close">✕</button>
        </div>
      </div>

      <div class="octa-tabs-bar">
        <button class="octa-tab-btn active" id="octa-tab-chat">💬 Live Assistant</button>
        <button class="octa-tab-btn" id="octa-tab-ticket">🎫 Raise Ticket</button>
      </div>

      <!-- Messages View -->
      <div id="octa-view-chat" style="display: flex; flex-direction: column; flex: 1; min-height: 0;">
        <div class="octa-messages-wrap" id="octa-messages">
          <div class="octa-bubble octa-bubble-agent" id="octa-welcome-msg">
            Hi there! How can we assist you today? Feel free to ask any question or request a live support agent.
          </div>
        </div>

        <div class="octa-quick-chips">
          <button class="octa-chip" id="octa-chip-human">👤 Talk to Human</button>
          <button class="octa-chip" id="octa-chip-pricing">Pricing & Plans</button>
          <button class="octa-chip" id="octa-chip-support">Technical Issue</button>
        </div>

        <div class="octa-input-wrap">
          <input type="text" class="octa-input" id="octa-input" placeholder="Type your question..." />
          <button class="octa-send-btn" id="octa-send-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </div>
      </div>

      <!-- Raise Ticket View -->
      <div id="octa-view-ticket" style="display: none; flex-direction: column; flex: 1; min-height: 0;">
        <div class="octa-ticket-form">
          <p style="font-size: 11px; color: #94a3b8; margin: 0 0 6px 0;">
            Leave your contact details and issue below. Our human support agents will follow up promptly via email or phone.
          </p>
          <div>
            <div class="octa-form-label">Problem Description *</div>
            <textarea class="octa-form-textarea" id="octa-form-problem" placeholder="Describe the issue you are facing..."></textarea>
          </div>
          <div>
            <div class="octa-form-label">Full Name *</div>
            <input type="text" class="octa-form-input" id="octa-form-name" placeholder="John Doe" />
          </div>
          <div>
            <div class="octa-form-label">Email Address *</div>
            <input type="email" class="octa-form-input" id="octa-form-email" placeholder="john@example.com" />
          </div>
          <div>
            <div class="octa-form-label">Mobile Number *</div>
            <input type="tel" class="octa-form-input" id="octa-form-phone" placeholder="+1 234 567 8900" />
          </div>
          <button class="octa-form-submit" id="octa-form-submit">Submit Priority Ticket</button>
          <div id="octa-form-feedback" style="font-size: 11px; text-align: center; margin-top: 4px;"></div>
        </div>
      </div>
    </div>

    <button class="octa-launcher-btn" id="octa-launcher-btn" title="Customer Support">
      <span class="octa-online-badge"></span>
      <svg id="octa-icon-open" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      <svg id="octa-icon-close" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:none;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
    </button>
  `;
  document.body.appendChild(rootEl);

  // 5. DOM References
  const windowEl = document.getElementById('octa-window');
  const launcherBtn = document.getElementById('octa-launcher-btn');
  const closeBtn = document.getElementById('octa-close-btn');
  const iconOpen = document.getElementById('octa-icon-open');
  const iconClose = document.getElementById('octa-icon-close');
  const titleEl = document.getElementById('octa-title');
  const statusText = document.getElementById('octa-status-text');
  const welcomeMsg = document.getElementById('octa-welcome-msg');
  const messagesWrap = document.getElementById('octa-messages');
  const inputEl = document.getElementById('octa-input');
  const sendBtn = document.getElementById('octa-send-btn');
  const tabChat = document.getElementById('octa-tab-chat');
  const tabTicket = document.getElementById('octa-tab-ticket');
  const viewChat = document.getElementById('octa-view-chat');
  const viewTicket = document.getElementById('octa-view-ticket');
  const chipHuman = document.getElementById('octa-chip-human');
  const chipPricing = document.getElementById('octa-chip-pricing');
  const chipSupport = document.getElementById('octa-chip-support');
  const formProblem = document.getElementById('octa-form-problem');
  const formName = document.getElementById('octa-form-name');
  const formEmail = document.getElementById('octa-form-email');
  const formPhone = document.getElementById('octa-form-phone');
  const formSubmit = document.getElementById('octa-form-submit');
  const formFeedback = document.getElementById('octa-form-feedback');

  // 6. Fetch Initial Config
  fetch(`${{apiPrefix}}/widget/config/${{tenantId}}`)
    .then(r => r.json())
    .then(data => {{
      widgetConfig = data;
      if (data.title) titleEl.textContent = data.title;
      if (data.welcome_message) welcomeMsg.textContent = data.welcome_message;
      if (data.live_chat_available) {{
        statusText.textContent = 'Live Support Available';
      }} else {{
        statusText.textContent = 'AI Support';
      }}
      if (data.brand_color) {{
        launcherBtn.style.background = `linear-gradient(135deg, ${{data.brand_color}}, #1d4ed8)`;
      }}
    }})
    .catch(e => console.error('[OctaOS Support] Config error:', e));

  // 7. Toggle Window
  function toggleWindow(open) {{
    isOpen = typeof open === 'boolean' ? open : !isOpen;
    if (isOpen) {{
      windowEl.classList.add('octa-open');
      iconOpen.style.display = 'none';
      iconClose.style.display = 'block';
      inputEl.focus();
      startPolling();
    }} else {{
      windowEl.classList.remove('octa-open');
      iconOpen.style.display = 'block';
      iconClose.style.display = 'none';
      stopPolling();
    }}
  }}

  launcherBtn.onclick = () => toggleWindow();
  closeBtn.onclick = () => toggleWindow(false);

  // 8. Tabs Switching
  tabChat.onclick = () => switchTab('chat');
  tabTicket.onclick = () => switchTab('ticket');

  function switchTab(tab) {{
    activeTab = tab;
    if (tab === 'chat') {{
      tabChat.classList.add('active');
      tabTicket.classList.remove('active');
      viewChat.style.display = 'flex';
      viewTicket.style.display = 'none';
    }} else {{
      tabTicket.classList.add('active');
      tabChat.classList.remove('active');
      viewChat.style.display = 'none';
      viewTicket.style.display = 'flex';
    }}
  }}

  // 9. Send Chat Message
  async function sendMessage(text, action) {{
    const message = (text || inputEl.value || '').trim();
    if (!message && !action) return;

    if (message) {{
      appendBubble(message, 'customer');
      inputEl.value = '';
    }}

    // Show typing
    const typingBubble = appendBubble('...', 'agent');
    typingBubble.id = 'octa-typing';

    try {{
      const res = await fetch(`${{apiPrefix}}/widget/message/${{tenantId}}`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          session_id: sessionId,
          message: message,
          action: action || 'chat',
        }})
      }});
      const data = await res.json();
      removeTyping();

      if (data.reply) {{
        aiShown[data.reply] = true;
        appendBubble(data.reply, 'agent', data.citations);
      }}

      // Check if handoff or out-of-context or loop suggested
      if (data.suggest_live_chat) {{
        appendHandoffSuggestion(data.reason, data.live_chat_available);
      }}

      // If action required: raise ticket
      if (data.action_required === 'raise_ticket') {{
        if (data.prefill) {{
          if (data.prefill.problem) formProblem.value = data.prefill.problem;
          if (data.prefill.name) formName.value = data.prefill.name;
          if (data.prefill.email) formEmail.value = data.prefill.email;
        }}
        setTimeout(() => switchTab('ticket'), 1200);
      }}

      if (data.status === 'handoff_queued') {{
        statusText.textContent = 'Connecting to Human...';
      }}

    }} catch (err) {{
      console.error(err);
      removeTyping();
      appendBubble("Sorry, we couldn't send your message. Please try again.", 'system');
    }}
  }}

  sendBtn.onclick = () => sendMessage();
  inputEl.onkeydown = (e) => {{
    if (e.key === 'Enter') sendMessage();
  }};

  chipHuman.onclick = () => {{
    sendMessage("I would like to speak with a human support agent.", "request_handoff");
  }};
  chipPricing.onclick = () => {{
    sendMessage("Can you explain your pricing and available plans?");
  }};
  chipSupport.onclick = () => {{
    sendMessage("I'm running into an issue and need technical support.");
  }};

  function appendBubble(content, type, citations) {{
    const bubble = document.createElement('div');
    bubble.className = `octa-bubble octa-bubble-${{type}}`;
    bubble.textContent = content;

    if (citations && citations.length > 0) {{
      const citEl = document.createElement('div');
      citEl.className = 'octa-citations';
      citEl.textContent = 'Sources: ' + citations.join('; ');
      bubble.appendChild(citEl);
    }}

    messagesWrap.appendChild(bubble);
    messagesWrap.scrollTop = messagesWrap.scrollHeight;
    return bubble;
  }}

  function removeTyping() {{
    const el = document.getElementById('octa-typing');
    if (el) el.remove();
  }}

  function appendHandoffSuggestion(reason, isAvailable) {{
    const box = document.createElement('div');
    box.className = 'octa-handoff-prompt';
    box.innerHTML = `
      <span>Need more help? Our live support team can take over.</span>
      <button class="octa-action-btn" id="octa-btn-connect-live">
        ${{isAvailable ? '💬 Connect to Live Chat' : '🎫 Raise Support Ticket'}}
      </button>
    `;
    messagesWrap.appendChild(box);
    messagesWrap.scrollTop = messagesWrap.scrollHeight;

    const btn = box.querySelector('#octa-btn-connect-live');
    if (btn) {{
      btn.onclick = () => {{
        if (isAvailable) {{
          sendMessage("Connect to live chat", "request_handoff");
        }} else {{
          switchTab('ticket');
        }}
      }};
    }}
  }}

  // 10. Form Submission
  formSubmit.onclick = async () => {{
    const problem = formProblem.value.trim();
    const name = formName.value.trim();
    const email = formEmail.value.trim();
    const phone = formPhone.value.trim();

    if (!problem || !name || !email || !phone) {{
      formFeedback.style.color = '#f87171';
      formFeedback.textContent = 'Please fill out all fields.';
      return;
    }}

    formSubmit.disabled = true;
    formFeedback.style.color = '#94a3b8';
    formFeedback.textContent = 'Submitting ticket...';

    try {{
      const res = await fetch(`${{apiPrefix}}/widget/raise-ticket/${{tenantId}}`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          session_id: sessionId,
          problem: problem,
          name: name,
          email: email,
          mobile_no: phone
        }})
      }});
      const data = await res.json();
      if (res.ok) {{
        formFeedback.style.color = '#34d399';
        formFeedback.textContent = '✅ Ticket created! We will contact you soon.';
        setTimeout(() => {{
          switchTab('chat');
          appendBubble(`Ticket #${{data.ticket_id ? data.ticket_id.substring(0, 8) : ''}} submitted successfully! Our team will get back to you shortly.`, 'system');
          formFeedback.textContent = '';
          formSubmit.disabled = false;
        }}, 1500);
      }} else {{
        formFeedback.style.color = '#f87171';
        formFeedback.textContent = data.detail || 'Failed to create ticket.';
        formSubmit.disabled = false;
      }}
    }} catch (e) {{
      formFeedback.style.color = '#f87171';
      formFeedback.textContent = 'Network error. Please try again.';
      formSubmit.disabled = false;
    }}
  }};

  // 11. Polling for Live Messages & Agent Status
  function startPolling() {{
    stopPolling();
    pollOnce();
    pollInterval = setInterval(pollOnce, 3000);
  }}

  function stopPolling() {{
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = null;
  }}

  async function pollOnce() {{
    try {{
      const res = await fetch(`${{apiPrefix}}/widget/poll/${{tenantId}}/${{sessionId}}`);
      if (!res.ok) return;
      const data = await res.json();

      if (data.ticket) {{
        ticketStatus = data.ticket.status;
        if (data.ticket.status === 'human_handling') {{
          statusText.textContent = data.ticket.agent_name ? `Live with ${{data.ticket.agent_name}}` : 'Live Agent Active';
        }} else if (data.ticket.status === 'pending_human') {{
          statusText.textContent = 'Waiting for Agent...';
        }} else if (data.ticket.status === 'resolved') {{
          statusText.textContent = 'AI Ready';
        }}
      }}

      // Render agent (human) and system messages we haven't shown yet
      if (data.messages && data.messages.length > 0) {{
        data.messages.forEach(m => {{
          if (renderedIds[m.id]) return;
          renderedIds[m.id] = true;
          if (m.sender === 'customer') return;
          // AI replies are already shown from the /message response
          if (m.sender === 'agent' && data.ticket && data.ticket.mode !== 'human' && data.ticket.status !== 'human_handling' && data.ticket.status !== 'resolved') return;
          if (m.sender === 'agent' && aiShown[m.content]) return;
          appendBubble(m.content, m.sender === 'system' ? 'system' : 'agent');
        }});
      }}
    }} catch (e) {{
      // ignore transient poll errors
    }}
  }}

}})();
"""
