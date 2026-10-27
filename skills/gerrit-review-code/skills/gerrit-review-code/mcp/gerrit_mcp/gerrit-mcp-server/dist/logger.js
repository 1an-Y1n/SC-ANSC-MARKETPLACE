import * as fs from 'fs';
import * as path from 'path';
let LOG_FILE = null;
export function getLogFilePath() {
    return LOG_FILE ?? '';
}
function ensureWritableLogLocation() {
    if (!LOG_FILE) {
        return;
    }
    const dirPath = path.dirname(LOG_FILE);
    try {
        if (!fs.existsSync(dirPath)) {
            fs.mkdirSync(dirPath, { recursive: true });
        }
        fs.accessSync(dirPath, fs.constants.W_OK);
    }
    catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        throw new Error(`Log directory is not writable: ${dirPath}. Log file: ${LOG_FILE}. Error: ${msg}`);
    }
    try {
        if (!fs.existsSync(LOG_FILE)) {
            fs.writeFileSync(LOG_FILE, '');
        }
        fs.accessSync(LOG_FILE, fs.constants.W_OK);
    }
    catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        throw new Error(`Log file is not writable: ${LOG_FILE}. Error: ${msg}`);
    }
}
export function setLogDirectory(logDir) {
    const normalized = logDir?.trim();
    if (!normalized) {
        LOG_FILE = null;
        return;
    }
    LOG_FILE = path.join(normalized, 'gerrit-mcp-server.log');
    ensureWritableLogLocation();
    fs.writeFileSync(LOG_FILE, '');
}
function ensureLogFileReady() {
    ensureWritableLogLocation();
}
export var LogLevel;
(function (LogLevel) {
    LogLevel["DEBUG"] = "DEBUG";
    LogLevel["INFO"] = "INFO";
    LogLevel["WARN"] = "WARN";
    LogLevel["ERROR"] = "ERROR";
})(LogLevel || (LogLevel = {}));
class Logger {
    static instance;
    constructor() {
    }
    static getInstance() {
        if (!Logger.instance) {
            Logger.instance = new Logger();
        }
        return Logger.instance;
    }
    formatMessage(level, message, data) {
        const timestamp = new Date().toISOString();
        let logMessage = `[${timestamp}] [${level}] ${message}`;
        if (data !== undefined) {
            if (typeof data === 'object') {
                logMessage += `\n${JSON.stringify(data, null, 2)}`;
            }
            else {
                logMessage += ` ${data}`;
            }
        }
        return logMessage + '\n';
    }
    writeLog(level, message, data) {
        if (!LOG_FILE) {
            return;
        }
        const logMessage = this.formatMessage(level, message, data);
        // Write to file
        ensureLogFileReady();
        fs.appendFileSync(LOG_FILE, logMessage, 'utf8');
    }
    debug(message, data) {
        this.writeLog(LogLevel.DEBUG, message, data);
    }
    info(message, data) {
        this.writeLog(LogLevel.INFO, message, data);
    }
    warn(message, data) {
        this.writeLog(LogLevel.WARN, message, data);
    }
    error(message, data) {
        this.writeLog(LogLevel.ERROR, message, data);
    }
    clearLog() {
        if (!LOG_FILE) {
            return;
        }
        fs.writeFileSync(LOG_FILE, '');
    }
}
// Export singleton instance
export const logger = Logger.getInstance();
//# sourceMappingURL=logger.js.map