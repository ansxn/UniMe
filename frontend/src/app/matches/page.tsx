"use client";
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import {
    currentQuizResultId,
    listSavedPrograms,
    programKey,
    queuePendingSave,
    quizSaveInProgress,
    saveCurrentQuizResult,
    saveProgram,
    unsaveProgram,
} from '@/lib/saved';
import { loginHref } from '@/lib/nav';
import './matches.css';

interface Match {
    school: string;
    program: string;
    overall: number;
    academic: number;
    campus: number;
    social: number;
}

interface Mentor {
    id: string;
    name: string;
    school: string;
    program: string;
    year: string;
    details: string;
    bio: string;
    avatar: string;
    linkedin: string;
}

// How closely the returned mentors relate to the selected program
type MentorMatch = 'program' | 'school' | 'general';

const MENTOR_HEADINGS: Record<MentorMatch, string> = {
    program: 'Connect with Student Mentors',
    school: 'Mentors at this school',
    general: "No mentors in this program yet — here are some UniMe mentors",
};

export default function Matches() {
    const [matches, setMatches] = useState<Match[]>([]);
    const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
    const [isDownloading, setIsDownloading] = useState(false);
    const [programMentors, setProgramMentors] = useState<Mentor[]>([]);
    const [mentorMatch, setMentorMatch] = useState<MentorMatch>('program');
    const [downloadError, setDownloadError] = useState<string | null>(null);

    // Accounts (all hidden when Supabase isn't configured)
    const router = useRouter();
    const { enabled: accountsEnabled, loading: authLoading, user, savedVersion } = useAuth();
    const [savedResultId, setSavedResultId] = useState<string | null>(null);
    const [saveState, setSaveState] = useState<'idle' | 'saving' | 'error'>('idle');
    const [starred, setStarred] = useState<Set<string>>(new Set());
    const [starBusy, setStarBusy] = useState<string | null>(null);

    useEffect(() => {
        try {
            const data = localStorage.getItem("matches");
            if (data) {
                const parsedData = JSON.parse(data);
                // Handle both possible response formats
                const matchesArray = parsedData.matches || parsedData;
                if (Array.isArray(matchesArray)) {
                    setMatches(matchesArray);
                }
            }
        } catch (error) {
            console.error("Error loading matches from localStorage:", error);
            setMatches([]);
        }
    }, []);

    // Is the current set of results already saved to the account?
    useEffect(() => {
        if (!accountsEnabled) return;
        setSavedResultId(currentQuizResultId());
        const inFlight = quizSaveInProgress();
        if (inFlight) {
            setSaveState('saving');
            inFlight
                .then(id => { setSavedResultId(id); setSaveState('idle'); })
                .catch(() => setSaveState('error'));
        }
    }, [accountsEnabled, user, savedVersion]);

    // Which programs this user has starred
    useEffect(() => {
        if (!user) {
            setStarred(new Set());
            return;
        }
        listSavedPrograms()
            .then(rows => setStarred(new Set(rows.map(r => programKey(r.school, r.program)))))
            .catch(err => console.error("Couldn't load saved programs:", err));
    }, [user, savedVersion]);

    const saveResults = async () => {
        if (!user) {
            queuePendingSave({ quiz: true });
            router.push(loginHref('/matches', { save: true, mode: 'signup' }));
            return;
        }
        setSaveState('saving');
        try {
            setSavedResultId(await saveCurrentQuizResult());
            setSaveState('idle');
        } catch (err) {
            console.error("Couldn't save results:", err);
            setSaveState('error');
        }
    };

    const toggleStar = async (match: Match) => {
        if (!user) {
            queuePendingSave({ programs: [match] });
            router.push(loginHref('/matches', { save: true }));
            return;
        }
        const key = programKey(match.school, match.program);
        const wasStarred = starred.has(key);
        setStarBusy(key);
        try {
            if (wasStarred) await unsaveProgram(match.school, match.program);
            else await saveProgram(match);
            setStarred(prev => {
                const next = new Set(prev);
                if (wasStarred) next.delete(key);
                else next.add(key);
                return next;
            });
        } catch (err) {
            console.error("Couldn't update saved program:", err);
        } finally {
            setStarBusy(null);
        }
    };

    const isStarred = (match: Match) => starred.has(programKey(match.school, match.program));

    function handleClick(match: Match) {
        setSelectedMatch(match);
    }

    const formatPercentage = (value: number) => {
        return `${Math.round(value * 100)}%`;
    };

    const fetchMentors = async (school: string, program: string) => {
        try {
            const params = new URLSearchParams({ school, program });
            const response = await fetch(`/api/program-mentors?${params}`);
            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const data: { match: MentorMatch; mentors: Mentor[] } = await response.json();
            setProgramMentors(data.mentors);
            setMentorMatch(data.match);
        } catch (error) {
            console.error("Error fetching mentors:", error);
            setProgramMentors([]);
        }
    };

    useEffect(() => {
        if (selectedMatch) {
            fetchMentors(selectedMatch.school, selectedMatch.program);
        }
    }, [selectedMatch]);

    const downloadPDF = async () => {
        try {
            setIsDownloading(true);

            setDownloadError(null);
            // Answers are saved by the quiz page on submit
            const answers = localStorage.getItem("answers");
            if (!answers) {
                setDownloadError("Retake the quiz to generate your full report.");
                return;
            }

            const response = await fetch('/api/report-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: answers,
            });
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `UniMe_matches_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

        } catch (error) {
            console.error('Error downloading PDF:', error);
            setDownloadError("Couldn't create your report. Please try again.");
        } finally {
            setIsDownloading(false);
        }
    };

    return (
        <div className="matches-container">
            <Link href="/" className="back-button">
                ← Back to Home
            </Link>
            <div className="matches-content">
                <div className="matches-header">
                    <p className="recommendations-label">Recommendations</p>
                    <h1 className="matches-title">Your Top Uni Matches</h1>
                    <p className="matches-subtitle">
                        Based on your answers, here are the university programs that
                        best match your interests and goals. Click on one to learn more!
                    </p>
                </div>
                <button
                    onClick={downloadPDF}
                    disabled={isDownloading}
                    className="fixed-download-button"
                >
                    {isDownloading ? (
                        'Downloading...'
                    ) : (
                        <>
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                width="20"
                                height="20"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                style={{ marginRight: '8px' }}
                            >
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="7 10 12 15 17 10"></polyline>
                                <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                            Download PDF Report
                        </>
                    )}
                </button>
                {accountsEnabled && !authLoading && matches.length > 0 && (
                    savedResultId ? (
                        <div className="save-prompt save-prompt-saved" role="status">
                            <div className="save-prompt-text">
                                <strong>Saved to your account</strong>
                                <span>Star programs below to keep a shortlist.</span>
                            </div>
                            <Link href="/account" className="acct-btn-ghost acct-btn-small">View account</Link>
                        </div>
                    ) : (
                        <div className="save-prompt">
                            <div className="save-prompt-text">
                                <strong>Save your results</strong>
                                <span>
                                    {user
                                        ? 'Keep these matches in your account so you can come back to them.'
                                        : "Create a free account to keep these matches and star programs. You'll come right back here."}
                                </span>
                            </div>
                            <div className="acct-actions">
                                {!user && (
                                    <Link
                                        href={loginHref('/matches', { save: true })}
                                        onClick={() => queuePendingSave({ quiz: true })}
                                        className="acct-btn-ghost acct-btn-small"
                                    >
                                        Log in
                                    </Link>
                                )}
                                <button
                                    type="button"
                                    className="acct-btn acct-btn-small"
                                    onClick={saveResults}
                                    disabled={saveState === 'saving'}
                                >
                                    {saveState === 'saving' ? 'Saving…' : user ? 'Save results' : 'Sign up to save'}
                                </button>
                            </div>
                            {saveState === 'error' && (
                                <p className="save-prompt-error" role="alert">Couldn&apos;t save right now. Please try again.</p>
                            )}
                        </div>
                    )
                )}
                {downloadError && (
                    <p role="alert" className="download-error">{downloadError}</p>
                )}

                <div className="matches-main">
                    <div className="match-list">
                        {matches.map((match, index) => (
                            <div
                                key={index}
                                className={`match ${selectedMatch === match ? 'selected' : ''}`}
                                onClick={() => handleClick(match)}
                            >
                                <h3 className="match-school">{match.school}</h3>
                                <p className="match-program">{match.program}</p>
                                <p className="match-score">Overall: {formatPercentage(match.overall)}</p>
                                {accountsEnabled && !authLoading && (
                                    <button
                                        type="button"
                                        className={`star-button ${isStarred(match) ? 'starred' : ''}`}
                                        aria-pressed={isStarred(match)}
                                        aria-label={`${isStarred(match) ? 'Remove' : 'Save'} ${match.program} at ${match.school}`}
                                        title={isStarred(match) ? 'Saved (click to remove)' : 'Save this program'}
                                        disabled={starBusy === programKey(match.school, match.program)}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            toggleStar(match);
                                        }}
                                    >
                                        {isStarred(match) ? '★' : '☆'}
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>

                    {selectedMatch && (
                        <div className="popup">
                            <div className="popup-header">
                                <h2>{selectedMatch.school}</h2>
                                <p className="program-subtitle">{selectedMatch.program}</p>
                                {accountsEnabled && !authLoading && (
                                    <div className="popup-star">
                                        <button
                                            type="button"
                                            className={`acct-btn-ghost acct-btn-small ${isStarred(selectedMatch) ? 'starred' : ''}`}
                                            aria-pressed={isStarred(selectedMatch)}
                                            disabled={starBusy === programKey(selectedMatch.school, selectedMatch.program)}
                                            onClick={() => toggleStar(selectedMatch)}
                                        >
                                            {isStarred(selectedMatch) ? '★ Saved program' : '☆ Save this program'}
                                        </button>
                                    </div>
                                )}
                            </div>

                            <div className="match-stats">
                                <h3>Your match statistics:</h3>
                                <div className="stats-grid">
                                    <span className="stat-item">Academics: {formatPercentage(selectedMatch.academic)}</span>
                                    <span className="stat-item">Social: {formatPercentage(selectedMatch.social)}</span>
                                    <span className="stat-item">Campus: {formatPercentage(selectedMatch.campus)}</span>
                                </div>
                            </div>

                            <div className="mentors-section">
                                <h3>{MENTOR_HEADINGS[mentorMatch]}</h3>
                                <div className="mentors-grid">
                                    {programMentors.length > 0 ? (
                                        programMentors.map((mentor, index) => (
                                            <div key={index} className="mentor-card">
                                                <h4>{mentor.name}</h4>
                                                <p className="mentor-details">{mentor.details}</p>
                                                <div
                                                    className="mentor-avatar"
                                                    style={{ backgroundImage: `url(${mentor.avatar})` }}
                                                ></div>
                                                <a
                                                    href={mentor.linkedin}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="mentor-button"
                                                >
                                                    MentorMe!
                                                </a>
                                            </div>
                                        ))
                                    ) : (
                                        <p>No mentors available for this program. Check back soon!</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}