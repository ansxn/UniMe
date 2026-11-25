"use client";
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import './chance.css';

interface ChanceMeFormData {
    school: string;
    program: string;
    top6: string;
    ecs: string;
}

interface SchoolOption {
    school: string;
    programs: string[];
}

type Prediction =
    | { found: false; reason: 'school' | 'program'; message: string }
    | {
        found: true;
        school: string;
        program: string;
        matched_programs: string[];
        sample_size: number;
        low_confidence: boolean;
        supp_required: boolean;
        user_average: number;
        ec_bonus: number;
        adjusted_average: number;
        offer_average: number;
        offer_min: number;
        offer_max: number;
        chance: number;
        verdict: string;
    };

const EMPTY_FORM: ChanceMeFormData = { school: '', program: '', top6: '', ecs: '' };

export default function ChanceMe() {
    const [formData, setFormData] = useState<ChanceMeFormData>(EMPTY_FORM);
    const [options, setOptions] = useState<SchoolOption[]>([]);
    const [result, setResult] = useState<Prediction | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetch('/api/chance-options')
            .then(res => (res.ok ? res.json() : []))
            .then(setOptions)
            .catch(() => setOptions([]));
    }, []);

    const programSuggestions = useMemo(
        () => options.find(o => o.school === formData.school)?.programs ?? [],
        [options, formData.school]
    );

    const handleInputChange = (field: keyof ChanceMeFormData, value: string) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const isFormValid = () => {
        const avg = Number(formData.top6);
        return formData.school.trim() !== '' &&
            formData.program.trim() !== '' &&
            formData.top6.trim() !== '' &&
            !isNaN(avg) && avg >= 0 && avg <= 100;
    };

    const handleSubmit = async () => {
        if (!isFormValid()) {
            setError('Please fill in all required fields with valid data');
            return;
        }

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const response = await fetch('/api/chance-me', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(formData),
            });
            const data = await response.json();
            if (data.success) {
                setResult(data.prediction);
            } else {
                setError(data.error || 'An error occurred');
            }
        } catch (err) {
            setError("We couldn't reach the server. Please try again in a moment.");
            console.error('Submit error:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setFormData(EMPTY_FORM);
        setResult(null);
        setError(null);
    };

    return (
        <div className="chance-container">
            <Link href="/" className="back-button">
                ← Back to Home
            </Link>
            <div className="header">
                <h1>calculate your chances</h1>
                <p className="subtext">Find your admission chances based on real admissions data. These results do not guarantee your acceptance.</p>
            </div>

            <div className="chance-me-content">
                <div className="form-container">
                    <div className="input-group">
                        <label htmlFor="school">University/School *</label>
                        {options.length > 0 ? (
                            <select
                                id="school"
                                value={formData.school}
                                onChange={(e) => setFormData(prev => ({ ...prev, school: e.target.value, program: '' }))}
                                className="form-input"
                            >
                                <option value="">Select a school…</option>
                                {options.map(o => (
                                    <option key={o.school} value={o.school}>{o.school}</option>
                                ))}
                            </select>
                        ) : (
                            <input
                                id="school"
                                type="text"
                                placeholder="e.g., Waterloo"
                                value={formData.school}
                                onChange={(e) => handleInputChange('school', e.target.value)}
                                className="form-input"
                            />
                        )}
                    </div>

                    <div className="input-group">
                        <label htmlFor="program">Program *</label>
                        <input
                            id="program"
                            type="text"
                            list="program-suggestions"
                            placeholder="e.g., Software Engineering"
                            value={formData.program}
                            onChange={(e) => handleInputChange('program', e.target.value)}
                            className="form-input"
                        />
                        <datalist id="program-suggestions">
                            {programSuggestions.map(p => <option key={p} value={p} />)}
                        </datalist>
                        <small className="input-help">Start typing to see programs we have data for</small>
                    </div>

                    <div className="input-group">
                        <label htmlFor="top6">Top 6 Average (%) *</label>
                        <input
                            id="top6"
                            type="number"
                            min="0"
                            max="100"
                            step="0.1"
                            placeholder="e.g., 95.5"
                            value={formData.top6}
                            onChange={(e) => handleInputChange('top6', e.target.value)}
                            className="form-input"
                        />
                    </div>

                    <div className="input-group">
                        <label htmlFor="ecs">Extracurriculars (optional)</label>
                        <input
                            id="ecs"
                            type="text"
                            placeholder="e.g., robotics, student council, volunteering"
                            value={formData.ecs}
                            onChange={(e) => handleInputChange('ecs', e.target.value)}
                            className="form-input"
                        />
                        <small className="input-help">Separate multiple activities with commas</small>
                    </div>

                    <div className="button-group">
                        <button
                            onClick={handleSubmit}
                            disabled={!isFormValid() || loading}
                            className={`submit-button ${!isFormValid() || loading ? 'disabled' : ''}`}
                        >
                            {loading ? 'Calculating...' : 'Calculate My Chances'}
                        </button>

                        <button
                            onClick={handleReset}
                            className="reset-button"
                            disabled={loading}
                        >
                            Reset Form
                        </button>
                    </div>

                    {error && (
                        <div className="error-message" role="alert">
                            ⚠️ {error}
                        </div>
                    )}
                </div>

                {result && (
                    <div className="result-container">
                        <h3>Your Admission Prediction</h3>
                        <div className="result-content">
                            {result.found ? (
                                <>
                                    <p className="result-chance">{result.chance}%</p>
                                    <p className="result-verdict">{result.verdict}</p>
                                    <dl className="result-details">
                                        <dt>Program</dt><dd>{result.program} at {result.school}</dd>
                                        <dt>Your average</dt>
                                        <dd>
                                            {result.user_average}%
                                            {result.ec_bonus > 0 && ` + ${result.ec_bonus}% EC bonus → ${result.adjusted_average}%`}
                                        </dd>
                                        <dt>Past offers</dt>
                                        <dd>avg {result.offer_average}% (range {result.offer_min}% – {result.offer_max}%)</dd>
                                        <dt>Based on</dt>
                                        <dd>{result.sample_size} reported offer{result.sample_size === 1 ? '' : 's'}</dd>
                                        <dt>Supplementary app</dt><dd>{result.supp_required ? 'Yes' : 'Not reported'}</dd>
                                    </dl>
                                    {result.low_confidence && (
                                        <p className="result-warning">
                                            Only a few past offers are on record for this program, so treat this estimate as rough.
                                        </p>
                                    )}
                                </>
                            ) : (
                                <p>⚠️ {result.message}</p>
                            )}
                        </div>
                        <div className="disclaimer">
                            <p>
                                <strong>Disclaimer:</strong> This prediction is based on historical data and should be used as a general guide only.
                                Actual admission decisions depend on many factors including essays, interviews, and current competition levels.
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
