"use client";
import { useState, useEffect } from 'react';
import Link from 'next/link';
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
                            </div>
                        ))}
                    </div>

                    {selectedMatch && (
                        <div className="popup">
                            <div className="popup-header">
                                <h2>{selectedMatch.school}</h2>
                                <p className="program-subtitle">{selectedMatch.program}</p>
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