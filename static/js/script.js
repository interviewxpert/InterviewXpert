class VoiceManager {
    constructor() {
        // Text-to-Speech
        this.speechSynthesis = window.speechSynthesis;

        // Speech-to-Text
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert('Speech recognition is not supported in this browser.');
            this.recognition = null;
        } else {
            this.recognition = new SpeechRecognition();
            this.isRecording = false;

            // Speech-to-Text Configuration
            this.recognition.lang = 'en-US';
            this.recognition.interimResults = true;
            this.recognition.maxAlternatives = 1;

            // Speech-to-Text Handlers
            this.recognition.onstart = () => {
                console.log('Voice recognition started. Speak into the microphone.');
            };

            this.recognition.onresult = (event) => {
                let transcript = '';
                for (let i = 0; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }
                document.getElementById('userAnswer').setAttribute('data-user-answer', transcript);
                document.getElementById('userAnswer').textContent = `Your Answer: ${transcript}`;
                console.log('Transcript:', transcript);
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                // alert('Speech recognition failed. Please try again.');
            };

            this.recognition.onend = () => {
                console.log('Voice recognition ended.');
                if (this.isRecording) {
                    console.log('Restarting recognition...');
                    this.recognition.start();
                }
            };
        }
    }

    // Text-to-Speech
    speakQuestion(question) {
        const utterance = new SpeechSynthesisUtterance(question);
        utterance.onstart = () => {
            console.log('Speech has started');
        };
        utterance.onend = () => {
            console.log('Speech has ended');
            $('#startVoiceBtn').show();
        };
        this.speechSynthesis.speak(utterance);
    }

    // Start Speech-to-Text
    startSpeechToText() {
        if (!this.recognition) return;
        this.recognition.start();
        this.isRecording = true;

        $('#startVoiceBtn').hide();
        $('#stopVoiceBtn').show();
    }

    // Stop Speech-to-Text
    stopSpeechToText() {
        if (this.recognition && this.isRecording) {
            this.recognition.stop();
            this.isRecording = false;

            $('#stopVoiceBtn').hide();
            $('#startVoiceBtn').show();

            return true;
        }

        return false;
    }

    // Stop All Voice Processes
    stopAllProcesses() {
        // Stop Text-to-Speech
        this.speechSynthesis.cancel();

        // Stop Speech-to-Text
        if (this.recognition && this.isRecording) {
            this.recognition.stop();
            this.isRecording = false;
        }
    }
}

const voiceManager = new VoiceManager();
var settings = {
    voiceEnabled: true
};

// Each Simulation Questions Log to keep track of the Questions asked
var simulationQuestionsLog = [];

function logQuestion(question, answer = null, report = null) {
    simulationQuestionsLog.push({ question, answer, report });
    console.log("Log updated:", simulationQuestionsLog);
}

$(document).ready(function () {
    $('#saveSettingsBtn').click(function () {
        const interviewType = $('#interviewType').val();
        const difficulty = $('#interviewDifficulty').val();
        const field = $('#interviewField').val();
        const length = $('#interviewLength').val();
        const feedbackFocus = $('#interviewFeedback').val();

        $.ajax({
            url: '/api/save-settings',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                interviewType,
                difficulty,
                field,
                length,
                feedbackFocus
            }),
            success: function (response) {
                if (response.success) {
                    $('#successMessage').show().delay(3000).fadeOut();
                    $('.settings-container').hide();
                    $('.simulation-step').show();
                }
            },
            error: function (error) {
                console.error('Error saving settings:', error);
            }
        });
    });

    $('#backToSettingsBtn').click(function () {
        $('.simulation-step').hide();
        $('.settings-container').show();
    });

    $('#startSimulationBtn').click(function () {
        $('.simulation-step').hide();

        startInterview();
    });

    $('#startVoiceBtn').click(function () {
        if (settings.voiceEnabled) {
            $('#userAnswer').html('')
            $('#userAnswer').show()
            $('#textAnswer').hide();
            voiceManager.startSpeechToText();
        }
    });
    $('#stopVoiceBtn').click(async function() { 
        var stopVoice = voiceManager.stopSpeechToText();
        
        if(stopVoice){
            question = $('#aiQuestion').text();
            answer = $('#userAnswer').attr('data-user-answer');
            report = await getAnswers(answer, question);
            if (report) {
                logQuestion(question, answer, report);
                console.log("Updated Log:", simulationQuestionsLog);
                $('#nextQuestion').show();
                compareLength();
            } else {
                console.error("Failed to fetch the report.");
            }
            $('#startVoiceBtn').prop('disabled', true);
        }
    });

    $('#endInterviewBtn').click(function () {
        alert("Interview ended.");
        $('.interview-interface').hide();
        $('.settings-container').show();
        $('#startVoiceBtn').hide();
        $('#nextQuestion').hide();
        $('#aiQuestion').attr('data-user-answer', '');
        $('#aiQuestion').html('');
        $('#userAnswer').html('').hide();
        $('#startVoiceBtn').prop('disabled', false);

        voiceManager.stopAllProcesses();

        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
            videoStream = null;
        }
    
        const videoElement = document.getElementById('userVideo');
        if (videoElement) {
            videoElement.srcObject = null;
        }
    });
});

    $('#nextQuestion').click(function() {
        $('#nextQuestion').hide();
        $('#startVoiceBtn').hide();
        $('#startVoiceBtn').prop('disabled', false);
        $('#aiQuestion').html('');
        $('#userAnswer').html('').hide();
        $('#userAnswer').attr('data-user-answer', '');
        
        getQuestion();
    });

    $('#finishInterviewBtn').click(function() {
        finishInterview();
    });

function initializeCount() {
    $.ajax({
        url: '/api/get-length',
        method: 'GET',
        success: function(response) {
            const length = response.length;
            // Save the length in sessionStorage
            sessionStorage.setItem('interviewLength', length);
        },
        error: function(err) {
            console.error('Error fetching interview length:', err);
            alert('Failed to load interview length.');
        }
    });
}

function compareLength(){
    const length = parseInt(sessionStorage.getItem('interviewLength'), 10);
    const questionsAsked = simulationQuestionsLog.length;

    if (questionsAsked >= length) {
        if (questionsAsked === length) {
            alert('This was the last question.');
        }
        $('#startVoiceBtn').hide();
        $('#nextQuestion').hide();
        $('#endInterviewBtn').hide();
        $('#finishInterviewBtn').show();
    }
}

function startInterview() {
    $('#consentModal').modal('show');
    
    $('#consentYes').off('click').on('click', function() {
        $('.interview-interface').show();
        $('#consentModal').modal('hide');
        
        initiliazeInterview();
    });

    $('#consentNo').off('click').on('click', function() {
        $('.interview-interface').hide();
        $('.simulation-step').show();
        $('#consentModal').modal('hide');
    });
}

function finishInterview() {
    // Save the log to the database
    $.ajax({
        url: '/api/save-log',
        method: 'POST',
        data: JSON.stringify({ questions_log: simulationQuestionsLog }),
        contentType: 'application/json',
        success: function(response) {
            var interview_id = response.interview_id;
            window.location.href = '/result?interview_id='+interview_id;
        },
        error: function(err) {
            console.error('Error saving log:', err);
            alert('Failed to save interview log.');
        }
    });
}


function initiliazeInterview() {

    // Enable Camera
    requestCameraAccess().then(() => {
        startInterviewWithServer();
    }).catch(error => {
        console.error('Error accessing media devices:', error);
        alert('You need to grant access to the camera and microphone for the interview.');
    });

    const question = "What is your experience with Python?";
    
    console.log("Interview started.");
}

// Camera Enabled Condition
let videoStream = null;
function requestCameraAccess() {
    return new Promise((resolve, reject) => {
        navigator.mediaDevices.getUserMedia({ video: true, audio: false })
            .then(stream => {
                videoStream = stream;
                const videoElement = document.getElementById('userVideo');
                videoElement.srcObject = stream;
                resolve();
            })
            .catch(err => {
                reject(err);
            });
    });
}

// Fetch Question
function startInterviewWithServer() {
    initializeCount();
    document.querySelector('.interview-interface').style.display = 'block';
    
    $.ajax({
        url: '/api/get-question',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            question: simulationQuestionsLog
        }),
        success: function(response) {
            // Initial Question
            const question = response.question;
            document.getElementById('aiQuestion').textContent = question;
            
            var webSpeech = voiceManager.speakQuestion(question);

            if(webSpeech){
                logQuestion(question);
                document.getElementById('nextQuestionBtn').style.display = 'block';
            }

        },
        error: function(err) {
            console.error('Error fetching question:', err);
            alert('Failed to load question.');
        }
    });
}

function getQuestion(){
    $.ajax({
        url: '/api/get-question',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            questions_log: simulationQuestionsLog
        }),
        success: function(response) {
            // Initial Question
            const question = response.question;
            document.getElementById('aiQuestion').textContent = question;
            
            var webSpeech = voiceManager.speakQuestion(question);

            if(webSpeech){
                logQuestion(question);
                document.getElementById('nextQuestionBtn').style.display = 'block';
            }

        },
        error: function(err) {
            console.error('Error fetching question:', err);
            alert('Failed to load question.');
        }
    });
}

async function getAnswers(question, answer) {
    try {
        const response = await $.ajax({
            url: '/api/get-answer',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                ix_question: question,
                ix_answer: answer
            })
        });
        console.log(response);
        if (response) {
            if (response.Correct) {
                return { Correct: response.Correct };
            } else if (response.Wrong) {
                return { Wrong: response.Wrong };
            } else {
                console.error("Unexpected AI response format:", response);
                return { error: "Invalid AI response format" };
            }
        } else {
            console.error("Invalid API response", response);
            return null;
        }
    } catch (error) {
        console.error("Error fetching answers:", error);
        return null;
    }
}