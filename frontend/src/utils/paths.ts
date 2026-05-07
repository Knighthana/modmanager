/** Path utility functions. */

/**
 * Ensure a directory path ends with a trailing slash.
 * @param path - The path to normalize.
 * @returns The path guaranteed to end with '/'.
 */
export function ensureTrailingSlash(path: string): string {
    return path.endsWith('/') ? path : path + '/';
}
