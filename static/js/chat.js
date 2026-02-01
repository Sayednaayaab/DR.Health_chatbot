// Chat functionality for Health Chatbot

document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatMessages = document.getElementById('chat-messages');
    const themeToggle = document.getElementById('theme-toggle');
    const newChatButton = document.getElementById('new-chat-button');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const mainContent = document.querySelector('.main-content');
    const conversationsList = document.getElementById('conversations-list');
    const conversationSearch = document.getElementById('conversation-search');
    const newConversationBtn = document.getElementById('new-conversation-btn');

    let currentConversationId = null;
    let chat_history = [];
    let follow_up_state = {};
    let allConversations = [];

    // Function to parse raw assistant response text into sections
    function parseResponse(text) {
        const sections = {};
        const lines = text.split('\n');
        let current_section = null;
        let follow_up_question = null;
        let follow_up_options = [];

        for (let line of lines) {
            line = line.trim();
            if (line.startsWith('FOLLOW-UP:')) {
                const follow_up_content = line.slice(11).trim();
                if (follow_up_content.includes('<') && follow_up_content.includes('>')) {
                    const question_part = follow_up_content.split('<')[0].trim();
                    const options_part = follow_up_content.split('<')[1].split('>')[0];
                    const options = options_part.split(',').map(opt => opt.trim());
                    follow_up_question = question_part;
                    follow_up_options = options;
                }
            } else if (line.startsWith('•') && line.includes(':')) {
                const section_title = line.slice(1).split(':')[0].trim();
                const content = line.split(':').slice(1).join(':').trim();
                sections[section_title] = content;
                current_section = section_title;
            } else if (current_section && line) {
                if (line.includes('<') && line.includes('>') && (line.includes('?') || line.toLowerCase().includes('temperature') || line.toLowerCase().includes('symptoms') || line.toLowerCase().includes('cough') || line.toLowerCase().includes('headache') || line.toLowerCase().includes('pain'))) {
                    const question_part = line.split('<')[0].trim();
                    const options_part = line.split('<')[1].split('>')[0];
                    const options = options_part.split(',').map(opt => opt.trim());
                    follow_up_question = question_part;
                    follow_up_options = options;
                } else {
                    sections[current_section] += ' ' + line;
                }
            }
        }

        if (Object.keys(sections).length === 0) {
            const section_keywords = [
                "Severity Assessment", "Differential Diagnosis", "Immediate Management",
                "Pharmacotherapy", "Preventive Measures", "Red Flags"
            ];
            current_section = null;
            for (let line of lines) {
                line = line.trim();
                if (!line) continue;
                let found = false;
                for (let keyword of section_keywords) {
                    if (line.toLowerCase().includes(keyword.toLowerCase())) {
                        current_section = keyword;
                        if (line.includes(':')) {
                            const colonIndex = line.indexOf(':');
                            const afterColon = line.slice(colonIndex + 1).trim();
                            sections[current_section] = afterColon;
                        } else {
                            sections[current_section] = "";
                        }
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    if (current_section) {
                        sections[current_section] += line + " ";
                    } else {
                        if (!sections["Response"]) sections["Response"] = "";
                        sections["Response"] += line + " ";
                    }
                }
            }
            if (Object.keys(sections).length === 0) {
                sections["Response"] = text.trim();
            }
        }

        if (follow_up_question) {
            sections["follow_up"] = {
                "question": follow_up_question,
                "options": follow_up_options
            };
        }

        return sections;
    }

    // Theme toggle functionality
    themeToggle.addEventListener('click', function() {
        const newTheme = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
        document.body.dataset.theme = newTheme;
        localStorage.setItem('theme', newTheme);
        themeToggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
    });

    // New chat functionality
    newChatButton.addEventListener('click', function() {
        // Create a new conversation
        fetch('/conversation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ title: 'New Conversation' }),
        })
        .then(response => response.json())
        .then(data => {
            currentConversationId = data.conversation_id;
            // Clear all chat messages
            chatMessages.innerHTML = '';
            // Reset backend chat history
            fetch('/reset', {
                method: 'POST',
            })
            .then(response => response.json())
            .then(data => {
                console.log('Chat reset:', data.message);
                loadConversations();
            })
            .catch(error => {
                console.error('Error resetting chat:', error);
            });
        })
        .catch(error => {
            console.error('Error creating conversation:', error);
        });
    });

    // Send message function
    function sendMessage() {
        const message = messageInput.value.trim();
        if (message === '') return;

        // Add user message to chat
        addMessage(message, 'user');
        messageInput.value = '';

        // Save user message to database if conversation exists
        if (currentConversationId) {
            saveMessageToDB(message, 'user');
        }

        // Show typing indicator
        showTypingIndicator();

        // Send message to backend
        const requestBody = { message: message };
        if (currentConversationId) {
            requestBody.conversation_id = currentConversationId;
        }
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
        })
        .then(response => response.json())
        .then(data => {
            // Remove typing indicator
            removeTypingIndicator();
            // Add bot response
            if (typeof data.response === 'object') {
                // Check for follow-up question
                if (data.response.follow_up) {
                    const followUp = data.response.follow_up;
                    delete data.response.follow_up; // Remove from sections
                    addMessageCards(data.response, 'bot');
                    addFollowUpForm(followUp);
                } else {
                    addMessageCards(data.response, 'bot');
                }
            } else {
                addMessage(data.response, 'bot');
            }

            // Save bot response to database if conversation exists
            if (currentConversationId) {
                const botResponse = typeof data.response === 'object' ? JSON.stringify(data.response) : data.response;
                saveMessageToDB(botResponse, 'assistant');
                // Refresh conversations list to update titles
                loadConversations();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            removeTypingIndicator();
            addMessage('Sorry, there was an error processing your request.', 'bot');
        });
    }

    // Add message to chat
    function addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;

        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Add message cards to chat
    function addMessageCards(sections, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const cardsContainer = document.createElement('div');
        cardsContainer.className = 'cards-container';

        for (const [section, content] of Object.entries(sections)) {
            if (section === 'follow_up') continue;
            const card = document.createElement('div');
            card.className = `card ${getCardClass(section, content)}`;

            const title = document.createElement('div');
            title.className = 'card-title';
            title.textContent = section;

            const body = document.createElement('div');
            body.className = 'card-body';
            body.textContent = content;

            card.appendChild(title);
            card.appendChild(body);
            cardsContainer.appendChild(card);
        }

        messageDiv.appendChild(cardsContainer);
        chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Get card class based on section for color coding
    function getCardClass(section, content = '') {
        if (!content || typeof content !== 'string') return 'default';
        const lowerSection = section.toLowerCase();
        const lowerContent = content.toLowerCase();

        // Debug logging
        console.log('Section:', section, 'Content:', content);

        // Check for severity sections - only these get dynamic colors
        if (lowerSection.includes('severity') || lowerSection.includes('assessment')) {
            // Dynamic color based on severity content
            if (lowerContent.includes('severe') || lowerContent.includes('critical') || lowerContent.includes('high') || lowerContent.includes('emergency') || lowerContent.includes('urgent')) {
                return 'red';
            } else if (lowerContent.includes('moderate') || lowerContent.includes('medium') || lowerContent.includes('caution') || lowerContent.includes('watch')) {
                return 'yellow';
            } else if (lowerContent.includes('mild') || lowerContent.includes('low') || lowerContent.includes('normal') || lowerContent.includes('stable')) {
                return 'green';
            } else {
                return 'yellow'; // default for severity
            }
        }

        // Check for medicine sections - only these get blue color
        if (lowerSection.includes('medicine') || lowerSection.includes('pharmacotherapy') || lowerSection.includes('drug') || lowerSection.includes('medication')) {
            return 'blue';
        }

        // All other sections get default color (no special styling)
        return 'default';
    }

    // Show typing indicator
    function showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';

        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.className = 'dot';
            indicator.appendChild(dot);
        }

        chatMessages.appendChild(indicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Remove typing indicator
    function removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    // Add follow-up question form
    function addFollowUpForm(followUpData) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message bot-message`;

        const formContainer = document.createElement('div');
        formContainer.className = 'follow-up-form';

        const questionDiv = document.createElement('div');
        questionDiv.className = 'follow-up-question';
        questionDiv.textContent = followUpData.question;

        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'follow-up-options';

        followUpData.options.forEach(option => {
            const button = document.createElement('button');
            button.className = 'follow-up-option';
            button.textContent = option;
            button.addEventListener('click', function() {
                // Send the selected option as a message
                sendMessageFromFollowUp(option);
                // Remove the form
                formContainer.remove();
            });
            optionsDiv.appendChild(button);
        });

        formContainer.appendChild(questionDiv);
        formContainer.appendChild(optionsDiv);
        messageDiv.appendChild(formContainer);
        chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Send message from follow-up selection
    function sendMessageFromFollowUp(selectedOption) {
        // Add user selection to chat
        addMessage(selectedOption, 'user');

        // Save user message to database if conversation exists
        if (currentConversationId) {
            saveMessageToDB(selectedOption, 'user');
        }

        // Show typing indicator
        showTypingIndicator();

        // Send the selection to backend
        const requestBody = { message: selectedOption };
        if (currentConversationId) {
            requestBody.conversation_id = currentConversationId;
        }
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
        })
        .then(response => response.json())
        .then(data => {
            // Remove typing indicator
            removeTypingIndicator();
            // Add bot response
            if (typeof data.response === 'object') {
                // Check for follow-up question
                if (data.response.follow_up) {
                    const followUp = data.response.follow_up;
                    delete data.response.follow_up; // Remove from sections
                    addMessageCards(data.response, 'bot');
                    addFollowUpForm(followUp);
                } else {
                    addMessageCards(data.response, 'bot');
                }
            } else {
                addMessage(data.response, 'bot');
            }

            // Set conversation_id if not set
            if (!currentConversationId && data.conversation_id) {
                currentConversationId = data.conversation_id;
                // Refresh conversations list to show the new conversation
                loadConversations();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            removeTypingIndicator();
            addMessage('Sorry, there was an error processing your request.', 'bot');
        });
    }

    // Load conversations on page load
    loadConversations();

    // Function to load conversations
    function loadConversations() {
        console.log('Loading conversations...');
        fetch('/conversations')
        .then(response => {
            console.log('Conversations fetch response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Conversations data received:', data);
            if (data.error) {
                console.error('Server error loading conversations:', data.error);
                return;
            }
            allConversations = data.conversations; // Store all conversations
            renderConversations(allConversations);
        })
        .catch(error => {
            console.error('Error loading conversations:', error);
        });
    }

    // Function to load a specific conversation
    async function loadConversation(convId) {
        try {
            console.log('Loading conversation:', convId);
            const response = await fetch(`/conversation/${convId}`);
            console.log('Fetch response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('Conversation data received:', data);
            if (data.error) {
                console.error('Server error:', data.error);
                addMessage('Error loading conversation: ' + data.error, 'bot');
                return;
            }
            currentConversationId = convId;
            // Update chat_history with loaded messages
            chat_history = data.conversation.messages.map(msg => ({role: msg.role, content: msg.content}));
            follow_up_state = {};
            chatMessages.innerHTML = '';

            // Highlight the active conversation
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
            });
            const activeItem = document.querySelector(`.conversation-item[data-conv-id="${convId}"]`);
            if (activeItem) {
                activeItem.classList.add('active');
            }

            console.log('Messages to display:', data.conversation.messages.length);
            data.conversation.messages.forEach((msg, index) => {
                console.log(`Message ${index}:`, msg);
                if (msg.role === 'user') {
                    addMessage(msg.content, 'user');
                } else if (msg.role === 'assistant') {
                    // Parse the assistant response if it's JSON
                    try {
                        const parsed = JSON.parse(msg.content);
                        if (typeof parsed === 'object') {
                            // Display exactly as original - with cards
                            addMessageCards(parsed, 'bot');
                        } else {
                            addMessage(parsed, 'bot');
                        }
                    } catch (e) {
                        // If not JSON, parse the raw text into sections
                        console.log('Raw assistant content:', msg.content);
                        const parsed = parseResponse(msg.content);
                        console.log('Parsed sections:', parsed);
                        addMessageCards(parsed, 'bot');
                    }
                }
            });

            // If no messages, show a message
            if (data.conversation.messages.length === 0) {
                addMessage('This conversation has no messages.', 'bot');
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
            addMessage('Failed to load conversation. Please try again.', 'bot');
        }
    }

    // Function to save message to database
    function saveMessageToDB(content, role) {
        if (!currentConversationId) return;

        fetch('/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: currentConversationId,
                content: content,
                role: role
            }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Message saved:', data);
        })
        .catch(error => {
            console.error('Error saving message:', error);
        });
    }

    // Function to delete a conversation
    function deleteConversation(convId) {
        fetch(`/conversation/${convId}`, {
            method: 'DELETE',
        })
        .then(response => response.json())
        .then(data => {
            console.log('Conversation deleted:', data.message);
            loadConversations(); // Reload the conversations list
            // If the deleted conversation was active, clear the chat
            if (currentConversationId === convId) {
                currentConversationId = null;
                chatMessages.innerHTML = '';
            }
        })
        .catch(error => {
            console.error('Error deleting conversation:', error);
            alert('Failed to delete conversation. Please try again.');
        });
    }

    // Function to delete all conversations
    function deleteAllConversations() {
        fetch('/conversations', {
            method: 'DELETE',
        })
        .then(response => response.json())
        .then(data => {
            console.log('All conversations deleted:', data.message);
            loadConversations(); // Reload the conversations list
            // Clear the current chat
            currentConversationId = null;
            chatMessages.innerHTML = '';
        })
        .catch(error => {
            console.error('Error deleting all conversations:', error);
            alert('Failed to delete all conversations. Please try again.');
        });
    }

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Search functionality
    conversationSearch.addEventListener('input', filterConversations);
});
