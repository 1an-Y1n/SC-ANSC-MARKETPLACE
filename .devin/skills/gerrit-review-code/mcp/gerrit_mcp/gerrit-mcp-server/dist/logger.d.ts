export declare function getLogFilePath(): string;
export declare function setLogDirectory(logDir?: string): void;
export declare enum LogLevel {
    DEBUG = "DEBUG",
    INFO = "INFO",
    WARN = "WARN",
    ERROR = "ERROR"
}
declare class Logger {
    private static instance;
    private constructor();
    static getInstance(): Logger;
    private formatMessage;
    private writeLog;
    debug(message: string, data?: any): void;
    info(message: string, data?: any): void;
    warn(message: string, data?: any): void;
    error(message: string, data?: any): void;
    clearLog(): void;
}
export declare const logger: Logger;
export {};
//# sourceMappingURL=logger.d.ts.map