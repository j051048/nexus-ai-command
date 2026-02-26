type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  level: LogLevel;
  timestamp: string;
  module: string;
  message: string;
  data?: unknown;
}

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const MIN_LEVEL: LogLevel = import.meta.env.DEV ? 'debug' : 'warn';

const CONSOLE_METHOD: Record<LogLevel, 'debug' | 'info' | 'warn' | 'error'> = {
  debug: 'debug',
  info: 'info',
  warn: 'warn',
  error: 'error',
};

function emit(entry: LogEntry): void {
  if (LEVEL_PRIORITY[entry.level] < LEVEL_PRIORITY[MIN_LEVEL]) return;

  const prefix = `[${entry.level.toUpperCase()}] [${entry.timestamp}] [${entry.module}]`;
  const method = CONSOLE_METHOD[entry.level];

  if (entry.data !== undefined) {
    console[method](prefix, entry.message, entry.data);
  } else {
    console[method](prefix, entry.message);
  }
}

export interface Logger {
  debug(message: string, data?: unknown): void;
  info(message: string, data?: unknown): void;
  warn(message: string, data?: unknown): void;
  error(message: string, data?: unknown): void;
}

export function createLogger(module: string): Logger {
  const log = (level: LogLevel) => (message: string, data?: unknown) => {
    emit({ level, timestamp: new Date().toISOString(), module, message, data });
  };

  return { debug: log('debug'), info: log('info'), warn: log('warn'), error: log('error') };
}

export const logger: Logger = createLogger('app');
