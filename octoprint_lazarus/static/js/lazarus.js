$(function () {

    function LazarusViewModel(parameters) {
        var self = this;
        var localFileInputSelector = "#lazarus-local-file-input";
        var dropzoneSelector = "#tab_plugin_lazarus .lazarus-file-dropzone";

        self.settingsViewModel = parameters[0];

        self.licenseValid = ko.observable(false);
        self.licenseBusy = ko.observable(false);
        self.licenseEmail = ko.observable("");
        self.licenseKey = ko.observable("");
        self.licenseStatusText = ko.observable("Checking license...");
        self.licenseDeviceCount = ko.observable("");
        self.licenseMaxDevices = ko.observable(3);
        self.licenseModel = ko.observable("");
        self.installId = ko.observable("");
        self.looseFromBed = ko.observable(false);
        self.bedClearConfirmed = ko.observable(false);
        self.printGluedInPlace = ko.observable(false);
        self.includeLandingPadSupports = ko.observable(false);
        self.includeSupportInterface = ko.observable(true);
        self.supportClearance = ko.observable(0.8);
        self.supportMoveCount = ko.observable(0);
        self.rejectedInsertionSupportMoves = ko.observable(0);
        self.rejectedDisconnectedSupportMoves = ko.observable(0);
        self.supportWarnings = ko.observableArray([]);
        self.landingPadBuilt = ko.observable(false);
        self.landingPadHeight = ko.observable(0);
        self.landingPadFileName = ko.observable("");
        self.landingPadInProgress = ko.observable(false);
        self.measuredHeight = ko.observable("");
        self.alignmentSide = ko.observable("left");
        self.xyJogStep = ko.observable(1);
        self.zJogStep = ko.observable(0.1);
        self.controlMode = ko.observable("octoprint");
        self.moonrakerMode = ko.observable(false);
        self.moonrakerModeLabel = ko.computed(function () {
            return self.moonrakerMode() ? "ON" : "OFF";
        });

        self.resumeBuilt = ko.observable(false);
        self.datumX = ko.observable("");
        self.datumY = ko.observable("");
        self.datumZ = ko.observable("");
        self.datumExtremeKey = ko.observable("");
        self.resumeLayerExtremePoints = ko.observableArray([]);
        self.alignmentChecksUnlocked = ko.observable(false);
        self.alignmentCheckInProgress = ko.observable(false);
        self.lastAlignmentCheckPointKey = ko.observable("");
        self.parkX = ko.observable("");
        self.parkY = ko.observable("");
        self.parkZ = ko.observable("");
        self.previewText = ko.observable("");
        self.resumeFileName = ko.observable("");
        self.motionAcknowledged = ko.observable(false);
        self.buildInProgress = ko.observable(false);
        self.safeStartApplied = ko.observable(false);
        self.attestCurrentCoordinates = ko.observable(false);
        self.useAssumedPositionCoordinates = ko.observable(false);
        self.availableFiles = ko.observableArray([]);
        self.selectedServerFilePath = ko.observable("");
        self.selectedFileLabel = ko.observable("No file selected");
        self.selectedSourceType = ko.observable("");
        self.uploadedGcodeText = ko.observable("");
        self.uploadedFileName = ko.observable("");
        self.isDraggingFile = ko.observable(false);

        self.userSelectedFile = false;
        self.uploadedFileObject = null;
        self.uploadedServerFilePath = "";

        self.canResume = ko.computed(function () {
            return self.resumeBuilt() && self.motionAcknowledged() && self.safeStartApplied();
        });

        self.canDownloadResume = ko.computed(function () {
            return self.resumeBuilt() && !!self.resumeFileName();
        });

        self.canEnterMeasuredHeight = ko.computed(function () {
            return true;
        });

        self.canBuildLandingPad = ko.computed(function () {
            var measuredHeight = parseFloat(self.measuredHeight());
            var supportClearance = parseFloat(self.supportClearance());
            var supportsReady = !self.includeLandingPadSupports() ||
                (measuredHeight > 0 && supportClearance >= 0);
            return self.looseFromBed() &&
                self.bedClearConfirmed() &&
                supportsReady &&
                hasSelectedFile() &&
                self.licenseValid() &&
                !self.landingPadInProgress();
        });

        self.canBuildResume = ko.computed(function () {
            return self.licenseValid() &&
                !self.buildInProgress() &&
                (!self.looseFromBed() || self.printGluedInPlace());
        });

        self.canLockDatum = ko.computed(function () {
            if (!self.resumeBuilt()) {
                return false;
            }

            if (self.looseFromBed()) {
                return true;
            }

            if (!self.alignmentChecksUnlocked()) {
                return true;
            }

            if (!self.datumExtremeKey() || !self.resumeLayerExtremePoints().length) {
                return true;
            }

            return self.lastAlignmentCheckPointKey() === self.datumExtremeKey();
        });

        self.alignmentCheckStatusText = ko.computed(function () {
            if (!self.alignmentChecksUnlocked()) {
                return "";
            }

            if (self.lastAlignmentCheckPointKey() === self.datumExtremeKey()) {
                return "Highlighted alignment point reached. Position Calibrated is available for the final lock.";
            }

            return "Optional: check the side points, then return to the highlighted alignment point before locking again.";
        });

        self.landingPadStatusText = ko.computed(function () {
            if (self.landingPadInProgress()) {
                return "Building and starting the landing pad print.";
            }
            if (self.landingPadBuilt()) {
                return "Landing pad ready: " + (self.landingPadFileName() || "landing_pad.gcode") +
                    " (" + parseFloat(self.landingPadHeight() || 0).toFixed(3) + " mm offset).";
            }
            return "No landing pad has been printed for this file yet.";
        });

        self.openActivationPage = function () {
            window.open(getActivationUrl(), "_blank", "noopener,noreferrer");
        };

        self.licenseDeviceSummary = ko.computed(function () {
            var count = self.licenseDeviceCount();
            var max = self.licenseMaxDevices() || 3;

            if (count === "" || count === null || typeof count === "undefined") {
                return "Device count will appear after activation.";
            }

            return count + " of " + max + " devices active.";
        });

        function notify(title, text, type) {
            new PNotify({
                title: title,
                text: text,
                type: type || "info"
            });
        }

        function api(cmd, payload) {
            return OctoPrint.simpleApiCommand("lazarus", cmd, payload || {});
        }

        function getPluginSettings() {
            if (self.settingsViewModel &&
                self.settingsViewModel.settings &&
                self.settingsViewModel.settings.plugins &&
                self.settingsViewModel.settings.plugins.lazarus) {
                return self.settingsViewModel.settings.plugins.lazarus;
            }

            return null;
        }

        function readPluginSetting(name) {
            var pluginSettings = getPluginSettings();

            if (pluginSettings && typeof pluginSettings[name] === "function") {
                return $.trim(pluginSettings[name]() || "");
            }

            return "";
        }

        function writePluginSetting(name, value) {
            var pluginSettings = getPluginSettings();

            if (pluginSettings && typeof pluginSettings[name] === "function") {
                pluginSettings[name](value || "");
            }
        }

        function getApiBaseUrl() {
            return window.API_BASEURL || ((window.BASEURL || "/") + "api/");
        }

        function getNormalizedEngineUrl() {
            var engineUrl = "";

            if (self.settingsViewModel &&
                self.settingsViewModel.settings &&
                self.settingsViewModel.settings.plugins &&
                getPluginSettings() &&
                typeof getPluginSettings().engine_url === "function") {
                engineUrl = readPluginSetting("engine_url");
            }

            if (!engineUrl || engineUrl === ("https://app." + "lazarus3dprint.com")) {
                engineUrl = "https://wizard.lazarus3dprint.com";
            }

            return engineUrl.replace(/\/+$/, "");
        }

        function getInstallId() {
            if (self.settingsViewModel &&
                self.settingsViewModel.settings &&
                self.settingsViewModel.settings.plugins &&
                getPluginSettings() &&
                typeof getPluginSettings().install_id === "function") {
                return readPluginSetting("install_id");
            }

            return self.installId();
        }

        function getFilesApiUrl() {
            return getApiBaseUrl() + "files/local?recursive=true";
        }

        function getResumeDownloadUrl() {
            return getApiBaseUrl() + "plugin/lazarus?download_resume=1&_ts=" + Date.now();
        }

        function getActivationUrl() {
            var url = getNormalizedEngineUrl() + "/activate";
            var installId = getInstallId();

            if (installId) {
                url += "?install_id=" + encodeURIComponent(installId);
            }

            return url;
        }

        function getRequestHeaders(method) {
            if (OctoPrint && typeof OctoPrint.getRequestHeaders === "function") {
                return OctoPrint.getRequestHeaders(method || "POST");
            }

            return {};
        }

        function getAjaxErrorMessage(xhr, fallbackText) {
            if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
                return xhr.responseJSON.error;
            }

            if (xhr && xhr.responseText) {
                return xhr.responseText;
            }

            if (xhr && xhr.status === 0) {
                return fallbackText + " The connection was reset before OctoPrint replied.";
            }

            return fallbackText;
        }

        function refreshLicenseFieldsFromSettings() {
            self.installId(getInstallId());
            self.licenseEmail(readPluginSetting("license_email"));
            self.licenseKey(readPluginSetting("license_key"));
        }

        function updateLicenseStatus(resp) {
            var valid = resp && resp.valid === true;

            self.licenseValid(valid);
            self.licenseModel(resp && resp.license_model ? resp.license_model : "");

            if (resp && resp.device_count != null) {
                self.licenseDeviceCount(resp.device_count);
            }

            if (resp && resp.max_devices != null) {
                self.licenseMaxDevices(resp.max_devices);
            }

            if (valid) {
                self.licenseStatusText("License active.");
                return;
            }

            self.licenseStatusText(resp && resp.error ? resp.error : "License required before generating resume output.");
        }

        function updateControlMode(mode) {
            var normalized = mode === "moonraker" ? "moonraker" : "octoprint";
            self.controlMode(normalized);
            self.moonrakerMode(normalized === "moonraker");
        }

        function formatCoordinate(value) {
            var number = parseFloat(value);
            return isFinite(number) ? number.toFixed(3) : "";
        }

        function createExtremePointList(extremes, datumKey) {
            var order = ["x_min", "x_max", "y_min", "y_max"];
            var points = [];

            $.each(order, function (_index, key) {
                var point = extremes && extremes[key];
                var x;
                var y;
                var z;

                if (!point) {
                    return;
                }

                x = parseFloat(point.x);
                y = parseFloat(point.y);
                z = parseFloat(point.z);

                if (!isFinite(x) || !isFinite(y) || !isFinite(z)) {
                    return;
                }

                points.push({
                    key: point.key || key,
                    label: point.label || key.replace("_", " ").toUpperCase(),
                    x: x,
                    y: y,
                    z: z,
                    safeZ: z + 5,
                    formattedX: formatCoordinate(x),
                    formattedY: formatCoordinate(y),
                    formattedZ: formatCoordinate(z),
                    formattedSafeZ: formatCoordinate(z + 5),
                    isDatum: point.is_datum === true || key === datumKey
                });
            });

            return points;
        }

        function resetAlignmentCheckState() {
            self.alignmentChecksUnlocked(false);
            self.alignmentCheckInProgress(false);
            self.lastAlignmentCheckPointKey("");
        }

        function resetResumeState() {
            self.resumeBuilt(false);
            self.datumX("");
            self.datumY("");
            self.datumZ("");
            self.datumExtremeKey("");
            self.resumeLayerExtremePoints([]);
            resetAlignmentCheckState();
            self.previewText("");
            self.resumeFileName("");
            self.buildInProgress(false);
            self.attestCurrentCoordinates(false);
            self.useAssumedPositionCoordinates(false);
            self.motionAcknowledged(false);
            self.safeStartApplied(false);
        }

        function resetLandingPadState() {
            self.bedClearConfirmed(false);
            self.printGluedInPlace(false);
            self.landingPadBuilt(false);
            self.landingPadHeight(0);
            self.landingPadFileName("");
            self.landingPadInProgress(false);
            self.supportMoveCount(0);
            self.rejectedInsertionSupportMoves(0);
            self.rejectedDisconnectedSupportMoves(0);
            self.supportWarnings([]);
        }

        function isSupportedGcodeName(name) {
            var lower = (name || "").toLowerCase();
            return lower.endsWith(".gcode") ||
                lower.endsWith(".gco") ||
                lower.endsWith(".gc") ||
                lower.endsWith(".g");
        }

        function setSelectedOctoPrintFile(path, label, isUserChoice) {
            var selectionChanged = self.selectedSourceType() !== "octoprint" ||
                self.selectedServerFilePath() !== path;

            if (!path) {
                clearSelectedFile(isUserChoice);
                return;
            }

            self.selectedSourceType("octoprint");
            self.selectedServerFilePath(path);
            self.selectedFileLabel(label || path);
            self.uploadedGcodeText("");
            self.uploadedFileName("");
            self.uploadedFileObject = null;
            self.uploadedServerFilePath = "";

            if (isUserChoice) {
                self.userSelectedFile = true;
            }

            if (selectionChanged) {
                resetResumeState();
                resetLandingPadState();
            }
        }

        function setSelectedUploadedFile(file) {
            self.selectedSourceType("device");
            self.selectedServerFilePath("");
            self.selectedFileLabel(file && file.name ? file.name : "No file selected");
            self.uploadedGcodeText("");
            self.uploadedFileName(file && file.name ? file.name : "");
            self.uploadedFileObject = file || null;
            self.uploadedServerFilePath = "";
            self.userSelectedFile = true;
            resetResumeState();
            resetLandingPadState();
        }

        function clearSelectedFile(markAsUserChoice) {
            var hadSelection = !!self.selectedSourceType() ||
                !!self.selectedServerFilePath() ||
                !!self.uploadedGcodeText();

            self.selectedSourceType("");
            self.selectedServerFilePath("");
            self.selectedFileLabel("No file selected");
            self.uploadedGcodeText("");
            self.uploadedFileName("");
            self.uploadedFileObject = null;
            self.uploadedServerFilePath = "";

            if (markAsUserChoice) {
                self.userSelectedFile = true;
            }

            if (hadSelection) {
                resetResumeState();
                resetLandingPadState();
            }
        }

        function findAvailableFileByPath(path) {
            var files = self.availableFiles();
            var index;

            for (index = 0; index < files.length; index += 1) {
                if (files[index].path === path) {
                    return files[index];
                }
            }

            return null;
        }

        function findAvailableFileByDropText(text) {
            var cleaned = $.trim(text || "");
            var files = self.availableFiles();
            var index;

            if (!cleaned) {
                return null;
            }

            cleaned = cleaned.replace(/^local\//, "");

            for (index = 0; index < files.length; index += 1) {
                if (files[index].path === cleaned || files[index].label === cleaned) {
                    return files[index];
                }
            }

            for (index = 0; index < files.length; index += 1) {
                if (files[index].label === cleaned.split("/").pop()) {
                    return files[index];
                }
            }

            return null;
        }

        function flattenFileEntries(entries, bucket, parentPath) {
            var index;
            var entry;
            var path;

            for (index = 0; index < (entries || []).length; index += 1) {
                entry = entries[index];
                path = entry.path || (parentPath ? parentPath + "/" + entry.name : entry.name);

                if (entry.type === "folder" && entry.children) {
                    flattenFileEntries(entry.children, bucket, path);
                    continue;
                }

                if (!path || !isSupportedGcodeName(path)) {
                    continue;
                }

                bucket.push({
                    path: path,
                    label: path
                });
            }
        }

        function updateParkFields(park) {
            if (!park) {
                return;
            }

            self.parkX(park.x != null ? park.x : "");
            self.parkY(park.y != null ? park.y : "");
            self.parkZ(park.z != null ? park.z : "");
        }

        function hasSelectedFile() {
            if (self.selectedSourceType() === "device") {
                return !!self.uploadedFileObject;
            }

            if (self.selectedSourceType() === "octoprint") {
                return !!self.selectedServerFilePath();
            }

            return false;
        }

        function applyCurrentFileFromStatus(currentFile) {
            if (self.userSelectedFile) {
                return;
            }

            if (currentFile && currentFile.supported && currentFile.path) {
                setSelectedOctoPrintFile(currentFile.path, currentFile.name || currentFile.path, false);
                return;
            }

            if (currentFile && currentFile.name) {
                self.selectedSourceType("");
                self.selectedServerFilePath("");
                self.selectedFileLabel(currentFile.name);
                return;
            }

            clearSelectedFile(false);
        }

        function readLocalFile(file) {
            if (!file) {
                return;
            }

            if (!isSupportedGcodeName(file.name)) {
                notify("File Error", "Only GCODE files are supported.", "error");
                return;
            }

            setSelectedUploadedFile(file);
        }

        function extractUploadedLocalPath(response, fallbackName) {
            if (response && response.files && response.files.local) {
                if (response.files.local.path) {
                    return response.files.local.path;
                }

                if (response.files.local.name) {
                    return response.files.local.name;
                }
            }

            if (response && response.path) {
                return response.path;
            }

            if (response && response.name) {
                return response.name;
            }

            return fallbackName || "";
        }

        function uploadSelectedDeviceFile() {
            var deferred = $.Deferred();
            var file = self.uploadedFileObject;
            var request;
            var formData;

            if (!file) {
                deferred.reject({
                    responseJSON: {
                        error: "No file selected."
                    }
                });
                return deferred.promise();
            }

            if (self.uploadedServerFilePath) {
                deferred.resolve({
                    path: self.uploadedServerFilePath
                });
                return deferred.promise();
            }

            if (OctoPrint.files && typeof OctoPrint.files.upload === "function") {
                request = OctoPrint.files.upload("local", file);
            } else {
                formData = new FormData();
                formData.append("file", file, file.name);
                request = $.ajax({
                    url: getApiBaseUrl() + "files/local",
                    type: "POST",
                    data: formData,
                    processData: false,
                    contentType: false,
                    headers: getRequestHeaders("POST"),
                    dataType: "json"
                });
            }

            request
                .done(function (response) {
                    var path = extractUploadedLocalPath(response, file.name);

                    if (!path) {
                        deferred.reject({
                            responseJSON: {
                                error: "Device file upload succeeded but OctoPrint did not return a file path."
                            }
                        });
                        return;
                    }

                    self.uploadedServerFilePath = path;
                    deferred.resolve({
                        path: path,
                        response: response
                    });
                })
                .fail(function (xhr) {
                    deferred.reject(xhr);
                });

            return deferred.promise();
        }

        function handleBuildResumeSuccess(resp) {
            if (!resp || !resp.ok) {
                notify("Error", resp && resp.error ? resp.error : "Resume build failed", "error");
                return;
            }

            self.attestCurrentCoordinates(false);
            self.useAssumedPositionCoordinates(false);
            self.safeStartApplied(false);

            if (resp.datum) {
                self.datumX(resp.datum.x != null ? resp.datum.x : "");
                self.datumY(resp.datum.y != null ? resp.datum.y : "");
                self.datumZ(resp.datum.z != null ? resp.datum.z : "");
                self.datumExtremeKey(resp.datum_extreme_key ||
                    (resp.datum.alignment_side === "right" ? "x_max" : "x_min"));
            }

            self.resumeLayerExtremePoints(createExtremePointList(
                resp.resume_layer_extremes,
                self.datumExtremeKey()
            ));
            resetAlignmentCheckState();

            if (resp.park) {
                updateParkFields(resp.park);
            }

            if (resp.file && resp.file.name) {
                self.selectedFileLabel(resp.file.name);
            }

            self.resumeFileName(resp.resume_file_name || "resume.gcode");
            self.previewText(resp.preview ? resp.preview.join("\n") : "");
            self.motionAcknowledged(false);
            self.resumeBuilt(true);

            notify("Resume G-code Ready", "The true alignment point has been calculated.", "notice");
        }

        function handleBuildLandingPadSuccess(resp) {
            if (!resp || !resp.ok) {
                notify("Error", resp && resp.error ? resp.error : "Landing pad build failed", "error");
                return;
            }

            if (resp.park) {
                updateParkFields(resp.park);
            }

            if (resp.file && resp.file.name) {
                self.selectedFileLabel(resp.file.name);
            }

            self.landingPadBuilt(true);
            self.landingPadHeight(resp.landing_pad_height || 0);
            self.landingPadFileName(resp.landing_pad_file_name || "landing_pad.gcode");
            self.supportMoveCount(resp.support_move_count || 0);
            self.rejectedInsertionSupportMoves(resp.rejected_insertion_support_moves || 0);
            self.rejectedDisconnectedSupportMoves(resp.rejected_disconnected_support_moves || 0);
            self.supportWarnings(resp.warnings || []);
            self.printGluedInPlace(false);
            resetResumeState();

            notify(
                "Landing Pad Started",
                resp.message || "The first-layer landing pad print has been started.",
                "notice"
            );
        }

        function requestBuildLandingPad(payload) {
            return api("build_landing_pad", payload)
                .done(function (resp) {
                    self.landingPadInProgress(false);
                    handleBuildLandingPadSuccess(resp);
                })
                .fail(function (xhr) {
                    self.landingPadInProgress(false);
                    notify(
                        "Error",
                        getAjaxErrorMessage(
                            xhr,
                            "Landing pad build request failed. If you selected a large local G-code file, wait a few seconds and try again."
                        ),
                        "error"
                    );
                });
        }

        function requestBuildResume(payload) {
            return api("build_resume", payload)
                .done(function (resp) {
                    self.buildInProgress(false);
                    handleBuildResumeSuccess(resp);
                })
                .fail(function (xhr) {
                    self.buildInProgress(false);
                    notify(
                        "Error",
                        getAjaxErrorMessage(
                            xhr,
                            "Resume build request failed. If you selected a large local G-code file, wait a few seconds and try again."
                        ),
                        "error"
                    );
                });
        }

        self.setPrintState = function (state) {
            var nextLooseFromBed = state === "loose";
            if (self.looseFromBed() === nextLooseFromBed) {
                return;
            }

            self.looseFromBed(nextLooseFromBed);
            resetResumeState();
            resetLandingPadState();
        };

        self.loadAvailableFiles = function () {
            var loader = null;

            if (OctoPrint.files && typeof OctoPrint.files.listForLocation === "function") {
                loader = OctoPrint.files.listForLocation("local", true);
            } else {
                loader = $.ajax({
                    url: getFilesApiUrl(),
                    type: "GET",
                    dataType: "json"
                });
            }

            loader
                .done(function (response) {
                    var files = [];
                    flattenFileEntries(response && response.files ? response.files : [], files, "");
                    files.sort(function (a, b) {
                        return a.label.localeCompare(b.label);
                    });
                    self.availableFiles(files);
                })
                .fail(function () {
                    self.availableFiles([]);
                });
        };

        self.loadStatus = function () {
            return api("status")
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        return;
                    }

                    if (resp.install_id) {
                        self.installId(resp.install_id);
                    }

                    updateControlMode(resp.control_mode);
                    updateParkFields(resp.park);
                    applyCurrentFileFromStatus(resp.current_file);
                });
        };

        self.setControlMode = function (desiredMode) {
            desiredMode = desiredMode === "moonraker" ? "moonraker" : "octoprint";
            api("set_control_mode", {
                control_mode: desiredMode
            })
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Error", resp && resp.error ? resp.error : "Control mode update failed", "error");
                        self.loadStatus();
                        return;
                    }

                    updateControlMode(resp.control_mode);
                    updateParkFields(resp.park);
                    self.attestCurrentCoordinates(false);
                    self.useAssumedPositionCoordinates(false);
                    self.safeStartApplied(false);
                    notify(
                        "Control Mode",
                        resp.moonraker_mode ? "Moonraker/Klipper mode enabled." : "OctoPrint mode enabled.",
                        "success"
                    );
                })
                .fail(function (xhr) {
                    notify("Error", getAjaxErrorMessage(xhr, "Control mode update failed"), "error");
                    self.loadStatus();
                });
        };

        self.toggleControlMode = function () {
            self.setControlMode(self.moonrakerMode() ? "octoprint" : "moonraker");
        };

        self.setXyJogStep = function (step) {
            self.xyJogStep(step);
        };

        self.setZJogStep = function (step) {
            self.zJogStep(step);
        };

        self.jogAxis = function (axis, distance) {
            api("jog_relative", {
                axis: axis,
                distance: distance
            })
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Jog", resp && resp.error ? resp.error : "Jog command failed", "error");
                    }
                })
                .fail(function (xhr) {
                    notify("Jog", getAjaxErrorMessage(xhr, "Jog command failed"), "error");
                });
        };

        self.testMoonraker = function () {
            api("test_moonraker")
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Moonraker Test", resp && resp.error ? resp.error : "Moonraker connection failed", "error");
                        return;
                    }

                    notify("Moonraker Connected", resp.message || "Moonraker connection succeeded.", "success");
                })
                .fail(function (xhr) {
                    notify("Moonraker Test", getAjaxErrorMessage(xhr, "Moonraker connection failed"), "error");
                });
        };

        self.openSafeResumeHomingPrompt = function () {
            self.loadStatus().always(function () {
                $("#safe-resume-homing-modal").modal("show");
            });
        };

        self.selectServerFile = function () {
            var path = self.selectedServerFilePath();
            var file = findAvailableFileByPath(path);

            if (!path) {
                clearSelectedFile(true);
                return;
            }

            setSelectedOctoPrintFile(path, file ? file.label : path, true);
        };

        self.openLocalFilePicker = function () {
            $(localFileInputSelector).trigger("click");
        };

        self.buildLandingPad = function () {
            var payload;

            if (self.landingPadInProgress()) {
                return;
            }

            if (!self.looseFromBed()) {
                notify("Landing Pad", "Switch print state to Loose From Bed first.", "error");
                return;
            }

            if (!hasSelectedFile()) {
                notify("Input Error", "No file selected.", "error");
                return;
            }

            if (!self.bedClearConfirmed()) {
                notify("Safety Check", "Confirm the build plate is clear first.", "error");
                return;
            }

            if (self.includeLandingPadSupports()) {
                if (!(parseFloat(self.measuredHeight()) > 0)) {
                    notify("Input Error", "Measured height is required to rebuild supports.", "error");
                    return;
                }
                if (!(parseFloat(self.supportClearance()) >= 0)) {
                    notify("Input Error", "Support clearance cannot be negative.", "error");
                    return;
                }
            }

            self.landingPadInProgress(true);
            self.landingPadBuilt(false);
            self.landingPadHeight(0);
            self.landingPadFileName("");
            self.printGluedInPlace(false);
            resetResumeState();

            payload = {
                bed_clear_confirmed: true,
                include_supports: self.includeLandingPadSupports(),
                include_support_interface: self.includeSupportInterface(),
                measured_height: parseFloat(self.measuredHeight()),
                alignment_side: self.alignmentSide(),
                support_clearance_mm: parseFloat(self.supportClearance())
            };

            if (self.selectedSourceType() === "device") {
                uploadSelectedDeviceFile()
                    .done(function (uploadInfo) {
                        payload.file_path = uploadInfo.path;
                        requestBuildLandingPad(payload);
                    })
                    .fail(function (xhr) {
                        self.landingPadInProgress(false);
                        notify(
                            "Error",
                            getAjaxErrorMessage(xhr, "Device file upload failed"),
                            "error"
                        );
                    });
                return;
            }

            if (self.selectedSourceType() === "octoprint") {
                payload.file_path = self.selectedServerFilePath();
            }

            requestBuildLandingPad(payload);
        };

        self.validateInputs = function () {
            var measuredHeight = parseFloat(self.measuredHeight());

            if (self.looseFromBed() && !self.printGluedInPlace()) {
                notify("Loose Bed Resume", "Print the landing pad and confirm the failed print is glued in place first.", "error");
                return false;
            }

            if (!measuredHeight || measuredHeight <= 0) {
                notify("Input Error", "Measured height required", "error");
                return false;
            }

            if (!hasSelectedFile()) {
                notify("Input Error", "No file selected.", "error");
                return false;
            }

            return true;
        };

        self.buildResume = function () {
            var payload;

            if (self.buildInProgress()) {
                return;
            }

            if (!self.validateInputs()) {
                return;
            }

            resetResumeState();
            self.buildInProgress(true);

            payload = {
                measured_height: parseFloat(self.measuredHeight()),
                alignment_side: self.alignmentSide(),
                height_offset_mm: self.looseFromBed() ? parseFloat(self.landingPadHeight() || 0) : 0
            };

            if (self.selectedSourceType() === "device") {
                uploadSelectedDeviceFile()
                    .done(function (uploadInfo) {
                        payload.file_path = uploadInfo.path;
                        requestBuildResume(payload);
                    })
                    .fail(function (xhr) {
                        self.buildInProgress(false);
                        notify(
                            "Error",
                            getAjaxErrorMessage(xhr, "Device file upload failed"),
                            "error"
                        );
                    });
                return;
            }

            if (self.selectedSourceType() === "octoprint") {
                payload.file_path = self.selectedServerFilePath();
            }

            requestBuildResume(payload);
        };

        self.applySafeResumeHoming = function () {
            var measuredHeight = parseFloat(self.measuredHeight());

            if (!measuredHeight || measuredHeight <= 0) {
                notify("Input Error", "Measured height required", "error");
                return;
            }

            api("safe_resume_homing", {
                measured_height: measuredHeight
            })
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Error", resp && resp.error ? resp.error : "Safe Resume Homing failed", "error");
                        return;
                    }

                    self.attestCurrentCoordinates(false);
                    self.useAssumedPositionCoordinates(false);
                    self.safeStartApplied(true);
                    $("#safe-resume-homing-modal").modal("hide");
                    notify("Safe Resume Homing", resp.message || "X/Y homing started.", "success");
                })
                .fail(function (xhr) {
                    notify("Error", getAjaxErrorMessage(xhr, "Safe Resume Homing failed"), "error");
                });
        };

        self.applyAssumedPosition = function () {
            api("apply_assumed_position")
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Error", resp && resp.error ? resp.error : "Assumed position command failed", "error");
                        self.useAssumedPositionCoordinates(false);
                        return;
                    }

                    if (resp.park) {
                        updateParkFields(resp.park);
                    }

                    self.attestCurrentCoordinates(false);
                    self.safeStartApplied(true);
                    $("#safe-resume-homing-modal").modal("hide");
                    notify("Assumed Position", resp.message || "Toolhead reference position applied.", "success");
                })
                .fail(function (xhr) {
                    self.useAssumedPositionCoordinates(false);
                    notify("Error", getAjaxErrorMessage(xhr, "Assumed position command failed"), "error");
                });
        };

        self.goToDatum = function () {
            resetAlignmentCheckState();
            $("#alignment-step-modal").modal("show");

            api("goto_datum", {
                x: self.datumX(),
                y: self.datumY(),
                z: self.datumZ()
            })
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Error", resp && resp.error ? resp.error : "Move failed", "error");
                        return;
                    }

                    notify(
                        "Alignment Point Reached",
                        "The toolhead is over the true alignment point and ready for precision alignment.",
                        "success"
                    );
                })
                .fail(function (xhr) {
                    notify("Error", getAjaxErrorMessage(xhr, "Move failed"), "error");
                });
        };

        self.moveToAlignmentCheckPoint = function (point) {
            if (!point) {
                return;
            }

            if (self.looseFromBed() || !self.alignmentChecksUnlocked()) {
                notify("Position Calibrated", "Lock the initial alignment before using side check moves.", "notice");
                return;
            }

            self.alignmentCheckInProgress(true);
            api("goto_alignment_check", {
                x: point.x,
                y: point.y,
                z: point.z
            })
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Check Move", resp && resp.error ? resp.error : "Check move failed", "error");
                        return;
                    }

                    self.lastAlignmentCheckPointKey(point.key);
                    self.motionAcknowledged(false);

                    notify(
                        "Alignment Check",
                        point.label + " reached at Z" + formatCoordinate(resp.safe_z || point.safeZ) + ".",
                        point.isDatum ? "success" : "notice"
                    );
                })
                .fail(function (xhr) {
                    notify("Check Move", getAjaxErrorMessage(xhr, "Check move failed"), "error");
                })
                .always(function () {
                    self.alignmentCheckInProgress(false);
                });
        };

        self.resetAlignmentZ = function () {
            api("reset_alignment_z")
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Error", resp && resp.error ? resp.error : "Z reset failed", "error");
                        return;
                    }

                    notify("Z Coordinate Reset", resp.message || "Z coordinate reset to 200 mm.", "success");
                })
                .fail(function (xhr) {
                    notify("Error", getAjaxErrorMessage(xhr, "Z reset failed"), "error");
                });
        };

        self.lockDatum = function () {
            if (!self.canLockDatum()) {
                notify(
                    "Position Calibrated",
                    "Return to the highlighted alignment point before locking the calibrated position.",
                    "notice"
                );
                return;
            }

            api("lock_datum", {
                x: self.datumX(),
                y: self.datumY(),
                z: self.datumZ()
            })
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Error", resp && resp.error ? resp.error : "Lock failed", "error");
                        return;
                    }

                    if (!self.alignmentChecksUnlocked() && !self.looseFromBed() && self.resumeLayerExtremePoints().length) {
                        self.alignmentChecksUnlocked(true);
                        self.lastAlignmentCheckPointKey("");
                        notify(
                            "Position Calibrated",
                            "Initial coordinates locked. Optional side checks are now available.",
                            "success"
                        );
                        return;
                    }

                    resetAlignmentCheckState();
                    $("#alignment-step-modal").modal("hide");
                    notify("Alignment Locked", resp.message || "True alignment point locked. You may now set the nozzle temperature.", "success");
                })
                .fail(function (xhr) {
                    notify("Error", getAjaxErrorMessage(xhr, "Lock failed"), "error");
                });
        };

        self.downloadResume = function () {
            var link;

            if (!self.canDownloadResume()) {
                notify("Resume File", "Build the resume G-code first.", "notice");
                return;
            }

            link = document.createElement("a");
            link.href = getResumeDownloadUrl();
            link.download = self.resumeFileName() || "resume.gcode";
            link.style.display = "none";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        };

        self.resumeNow = function () {
            if (!self.safeStartApplied()) {
                notify("Safety", "Complete Safe Resume Homing, use assumed coordinates, or attest the current coordinate state before resuming.", "notice");
                return;
            }

            if (!self.motionAcknowledged()) {
                notify("Safety", "Confirm that printer motion is safe before resuming.", "notice");
                return;
            }

            api("execute_resume")
                .done(function (resp) {
                    if (!resp || resp.ok !== true) {
                        notify("Error", resp && resp.error ? resp.error : "Resume failed", "error");
                        return;
                    }

                    notify("The Helm", resp.message || "Resume sequence started", "success");
                })
                .fail(function (xhr) {
                    notify("Error", getAjaxErrorMessage(xhr, "Resume failed"), "error");
                });
        };

        self.validateLicense = function () {
            api("validate")
                .done(function (resp) {
                    updateLicenseStatus(resp);
                })
                .fail(function () {
                    self.licenseValid(false);
                    self.licenseStatusText("License check failed. Check the license service URL and internet access.");
                });
        };

        self.activateLicense = function () {
            var email = $.trim(self.licenseEmail() || "");
            var licenseKey = $.trim(self.licenseKey() || "");

            if (!email || !licenseKey) {
                notify("Activation", "Enter the checkout email and license key first.", "notice");
                return;
            }

            self.licenseBusy(true);
            api("activate_license", {
                email: email,
                license_key: licenseKey
            })
                .done(function (resp) {
                    self.licenseBusy(false);

                    if (!resp || resp.ok !== true || resp.valid !== true) {
                        updateLicenseStatus(resp || {});
                        notify("Activation", resp && resp.error ? resp.error : "Activation failed.", "error");
                        return;
                    }

                    writePluginSetting("license_email", email);
                    writePluginSetting("license_key", licenseKey);
                    updateLicenseStatus(resp);
                    notify("Activation", "This OctoPrint install is active.", "success");
                })
                .fail(function (xhr) {
                    self.licenseBusy(false);
                    self.licenseValid(false);
                    self.licenseStatusText(getAjaxErrorMessage(xhr, "Activation failed."));
                    notify("Activation", getAjaxErrorMessage(xhr, "Activation failed."), "error");
                });
        };

        self.recoverLicenseKey = function () {
            var email = $.trim(self.licenseEmail() || "");

            if (!email) {
                notify("License Key", "Enter the checkout email first.", "notice");
                return;
            }

            self.licenseBusy(true);
            api("recover_license_key", {
                email: email
            })
                .done(function (resp) {
                    self.licenseBusy(false);

                    if (!resp || resp.ok !== true || !resp.license_key) {
                        updateLicenseStatus(resp || {});
                        notify("License Key", resp && resp.error ? resp.error : "License key lookup failed.", "error");
                        return;
                    }

                    self.licenseKey(resp.license_key);
                    writePluginSetting("license_email", email);
                    writePluginSetting("license_key", resp.license_key);
                    updateLicenseStatus(resp);
                    notify("License Key", "License key loaded for this install.", "success");
                })
                .fail(function (xhr) {
                    self.licenseBusy(false);
                    self.licenseStatusText(getAjaxErrorMessage(xhr, "License key lookup failed."));
                    notify("License Key", getAjaxErrorMessage(xhr, "License key lookup failed."), "error");
                });
        };

        self.deactivateDevice = function () {
            var email = $.trim(self.licenseEmail() || "");
            var licenseKey = $.trim(self.licenseKey() || "");

            if (!email || !licenseKey) {
                notify("Deactivate", "Enter the checkout email and license key first.", "notice");
                return;
            }

            self.licenseBusy(true);
            api("deactivate_device", {
                email: email,
                license_key: licenseKey
            })
                .done(function (resp) {
                    self.licenseBusy(false);

                    if (!resp || resp.ok !== true) {
                        notify("Deactivate", resp && resp.error ? resp.error : "Device deactivation failed.", "error");
                        return;
                    }

                    self.licenseValid(false);
                    if (resp.device_count != null) {
                        self.licenseDeviceCount(resp.device_count);
                    }
                    if (resp.max_devices != null) {
                        self.licenseMaxDevices(resp.max_devices);
                    }
                    self.licenseStatusText("This OctoPrint install has been deactivated.");
                    notify("Deactivate", "This device was removed from the license.", "success");
                })
                .fail(function (xhr) {
                    self.licenseBusy(false);
                    notify("Deactivate", getAjaxErrorMessage(xhr, "Device deactivation failed."), "error");
                });
        };

        self.attestCurrentCoordinates.subscribe(function (isAttested) {
            if (isAttested) {
                self.useAssumedPositionCoordinates(false);
                self.safeStartApplied(true);
                return;
            }

            if (!self.useAssumedPositionCoordinates()) {
                self.safeStartApplied(false);
            }
        });

        self.useAssumedPositionCoordinates.subscribe(function (useAssumedPosition) {
            if (useAssumedPosition) {
                self.applyAssumedPosition();
                return;
            }

            if (!self.attestCurrentCoordinates()) {
                self.safeStartApplied(false);
            }
        });

        self.bindFilePicker = function () {
            $(document).off("change.lazarus", localFileInputSelector);
            $(document).on("change.lazarus", localFileInputSelector, function (event) {
                var files = event.target.files || [];
                if (files.length) {
                    readLocalFile(files[0]);
                }
                event.target.value = "";
            });
        };

        self.bindDropzone = function () {
            $(document).off("dragenter.lazarus dragover.lazarus dragleave.lazarus drop.lazarus", dropzoneSelector);

            $(document).on("dragenter.lazarus dragover.lazarus", dropzoneSelector, function (event) {
                event.preventDefault();
                event.stopPropagation();
                self.isDraggingFile(true);
            });

            $(document).on("dragleave.lazarus", dropzoneSelector, function (event) {
                event.preventDefault();
                event.stopPropagation();
                self.isDraggingFile(false);
            });

            $(document).on("drop.lazarus", dropzoneSelector, function (event) {
                var nativeEvent = event.originalEvent;
                var transfer = nativeEvent ? nativeEvent.dataTransfer : null;
                var droppedFile;
                var droppedText;
                var matchedFile;

                event.preventDefault();
                event.stopPropagation();
                self.isDraggingFile(false);

                if (!transfer) {
                    return;
                }

                if (transfer.files && transfer.files.length) {
                    droppedFile = transfer.files[0];
                    readLocalFile(droppedFile);
                    return;
                }

                droppedText = transfer.getData("text/plain") || transfer.getData("text/uri-list");
                matchedFile = findAvailableFileByDropText(droppedText);

                if (matchedFile) {
                    self.selectedServerFilePath(matchedFile.path);
                    setSelectedOctoPrintFile(matchedFile.path, matchedFile.label, true);
                    return;
                }

                notify("File Error", "Only GCODE files can be dropped here.", "error");
            });
        };

        self.onAfterBinding = function () {
            self.bindFilePicker();
            self.bindDropzone();
        };

        self.onStartupComplete = function () {
            refreshLicenseFieldsFromSettings();
            self.validateLicense();
            self.loadStatus();
            self.loadAvailableFiles();
        };

        self.onTabChange = function (current) {
            if (current === "#tab_plugin_lazarus") {
                refreshLicenseFieldsFromSettings();
                self.validateLicense();
                self.loadStatus();
                self.loadAvailableFiles();
            }
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: LazarusViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_lazarus"]
    });

});
