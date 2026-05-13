(function () {
    var currentUtterance = null;

    function getVoiceSelect() {
        return document.getElementById("speech-voice");
    }

    function setStatus(text) {
        var status = document.getElementById("speech-status");
        if (status) {
            status.innerText = "読み上げ状態: " + text;
        }
    }

    function getSelectedNumber(id, fallback) {
        var element = document.getElementById(id);
        if (!element) {
            return fallback;
        }
        var value = parseFloat(element.value);
        return Number.isFinite(value) ? value : fallback;
    }

    function postForm(form) {
        return fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        }).then(function (response) {
            return response.json().then(function (payload) {
                if (!response.ok) {
                    throw payload;
                }
                return payload;
            });
        });
    }

    function pollJob(jobUrl, onProgress, onComplete, onError) {
        var pollInterval = 2500;
        function poll() {
            fetch(jobUrl, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
                .then(function (response) {
                    return response.json();
                })
                .then(function (payload) {
                    if (payload.status === "completed") {
                        onComplete(payload);
                        return;
                    }
                    if (payload.status === "failed") {
                        onError(payload);
                        return;
                    }
                    onProgress(payload);
                    window.setTimeout(poll, pollInterval);
                })
                .catch(function () {
                    onError({ error: "ジョブ状態の確認に失敗しました。" });
                });
        }
        poll();
    }

    function setAudioButtonBusy(button, busy, text) {
        if (!button) {
            return;
        }
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }
        button.disabled = busy;
        if (busy) {
            button.textContent = text || "生成中...";
            button.setAttribute("aria-busy", "true");
            return;
        }
        button.textContent = text || button.dataset.originalText || "高品質音声を生成";
        button.removeAttribute("aria-busy");
    }

    function watchAudioJob(jobUrl, form, status) {
        var submitButton = form ? form.querySelector("button[type='submit']") : null;
        setAudioButtonBusy(submitButton, true, "生成中...");
        setAudioStatus(status, "生成中");
        pollJob(
            jobUrl,
            function () {
                setAudioStatus(status, "生成中");
            },
            function (jobPayload) {
                setAudioStatus(status, "完了");
                if (jobPayload.audio_url || (jobPayload.result && jobPayload.result.audio_url)) {
                    window.location.reload();
                    return;
                }
                setAudioButtonBusy(submitButton, false);
            },
            function (jobPayload) {
                setAudioStatus(status, jobPayload.error || "生成に失敗しました。");
                setAudioButtonBusy(submitButton, false);
            }
        );
    }

    function getAudioStatusElement(form) {
        if (!form) {
            return null;
        }
        return form.querySelector("[data-audio-status]") || document.getElementById("audio-generation-status");
    }

    function setAudioStatus(status, text) {
        if (!status) {
            return;
        }
        if (status.id === "audio-generation-status") {
            status.innerText = "高品質音声の生成状態: " + text;
            return;
        }
        status.innerText = text;
    }

    function getVoices() {
        if (!("speechSynthesis" in window)) {
            return [];
        }
        return speechSynthesis.getVoices();
    }

    function findJapaneseVoice() {
        var voiceSelect = getVoiceSelect();
        var voices = getVoices();
        if (voiceSelect && voiceSelect.value) {
            return voices.find(function (voice) {
                return voice.name === voiceSelect.value;
            });
        }
        return voices.find(function (voice) {
            return voice.lang && voice.lang.toLowerCase().startsWith("ja");
        });
    }

    function populateVoiceSelect() {
        var voiceSelect = getVoiceSelect();
        if (!voiceSelect) {
            return;
        }
        var voices = getVoices();
        voiceSelect.innerHTML = "";
        voices
            .slice()
            .sort(function (a, b) {
                var aIsJapanese = a.lang && a.lang.toLowerCase().startsWith("ja");
                var bIsJapanese = b.lang && b.lang.toLowerCase().startsWith("ja");
                if (aIsJapanese === bIsJapanese) {
                    return a.name.localeCompare(b.name);
                }
                return aIsJapanese ? -1 : 1;
            })
            .forEach(function (voice) {
                var option = document.createElement("option");
                option.value = voice.name;
                option.textContent = voice.name + " (" + voice.lang + ")";
                voiceSelect.appendChild(option);
            });
    }

    function speak(text) {
        if (!text || !("speechSynthesis" in window)) {
            setStatus("SpeechSynthesis非対応");
            return;
        }
        speechSynthesis.cancel();
        var utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "ja-JP";
        utterance.rate = getSelectedNumber("speech-rate", 0.9);
        utterance.pitch = getSelectedNumber("speech-pitch", 1.0);
        utterance.volume = getSelectedNumber("speech-volume", 1.0);
        var voice = findJapaneseVoice();
        if (voice) {
            utterance.voice = voice;
        }
        utterance.onstart = function () {
            setStatus("読み上げ中");
        };
        utterance.onpause = function () {
            setStatus("一時停止中");
        };
        utterance.onresume = function () {
            setStatus("読み上げ中");
        };
        utterance.onend = function () {
            setStatus("完了");
        };
        utterance.onerror = function () {
            setStatus("エラー");
        };
        currentUtterance = utterance;
        speechSynthesis.speak(utterance);
    }

    document.addEventListener("click", function (event) {
        var speakButton = event.target.closest("[data-speak]");
        var targetButton = event.target.closest("[data-speak-target]");
        if (speakButton) {
            speak(speakButton.dataset.speak);
        }
        if (targetButton) {
            var target = document.getElementById(targetButton.dataset.speakTarget);
            speak(target ? target.innerText : "");
        }
        if (event.target.closest("[data-stop-speech]")) {
            speechSynthesis.cancel();
            currentUtterance = null;
            setStatus("停止中");
        }
        if (event.target.closest("[data-pause-speech]")) {
            speechSynthesis.pause();
            if (currentUtterance) {
                setStatus("一時停止中");
            }
        }
        if (event.target.closest("[data-resume-speech]")) {
            speechSynthesis.resume();
            if (currentUtterance) {
                setStatus("読み上げ中");
            }
        }
    });

    if ("speechSynthesis" in window) {
        populateVoiceSelect();
        speechSynthesis.onvoiceschanged = populateVoiceSelect;
    } else {
        setStatus("SpeechSynthesis非対応");
    }

    var initialAudioForm = document.querySelector("[data-audio-form][data-pending-job-url]");
    if (initialAudioForm) {
        watchAudioJob(
            initialAudioForm.dataset.pendingJobUrl,
            initialAudioForm,
            getAudioStatusElement(initialAudioForm)
        );
    }
    document.querySelectorAll("[data-audio-form][data-pending-job-url]").forEach(function (form) {
        if (form !== initialAudioForm) {
            watchAudioJob(form.dataset.pendingJobUrl, form, getAudioStatusElement(form));
        }
    });

    document.addEventListener("submit", function (event) {
        var summaryForm = event.target.closest("[data-summary-form]");
        if (summaryForm) {
            event.preventDefault();
            var submitButton = summaryForm.querySelector("button[type='submit']");
            if (submitButton && !submitButton.disabled) {
                submitButton.dataset.originalText = submitButton.textContent;
                submitButton.textContent = "受付中...";
                submitButton.disabled = true;
                submitButton.setAttribute("aria-busy", "true");
            }
            postForm(summaryForm)
                .then(function (payload) {
                    if (submitButton) {
                        submitButton.textContent = "生成中...";
                    }
                    pollJob(
                        payload.job_url,
                        function () {},
                        function () {
                            window.location.reload();
                        },
                        function (jobPayload) {
                            if (submitButton) {
                                submitButton.textContent = submitButton.dataset.originalText || "ラジオ原稿を作成";
                                submitButton.disabled = false;
                                submitButton.removeAttribute("aria-busy");
                            }
                            window.alert(jobPayload.error || "ラジオ原稿の生成に失敗しました。");
                        }
                    );
                })
                .catch(function (payload) {
                    if (submitButton) {
                        submitButton.textContent = submitButton.dataset.originalText || "ラジオ原稿を作成";
                        submitButton.disabled = false;
                        submitButton.removeAttribute("aria-busy");
                    }
                    window.alert(payload.error || "ラジオ原稿の生成を開始できませんでした。");
                });
            return;
        }

        var form = event.target.closest("[data-audio-form]");
        if (!form) {
            return;
        }
        event.preventDefault();
        var submitButton = form.querySelector("button[type='submit']");
        if (submitButton && submitButton.disabled) {
            return;
        }
        var status = getAudioStatusElement(form);
        setAudioButtonBusy(submitButton, true, "生成中...");
        setAudioStatus(status, "生成中");
        postForm(form)
            .then(function (payload) {
                if (payload.status === "queued") {
                    setAudioStatus(status, "受付済み");
                    watchAudioJob(payload.job_url, form, status);
                    return;
                }
                setAudioStatus(status, payload.reused ? "既存音声を再利用しました" : "完了");
                if (payload.audio_url) {
                    window.location.reload();
                    return;
                }
                setAudioButtonBusy(submitButton, false);
            })
            .catch(function (payload) {
                setAudioStatus(status, payload.error || "生成に失敗しました。");
                setAudioButtonBusy(submitButton, false);
            });
    });
})();
