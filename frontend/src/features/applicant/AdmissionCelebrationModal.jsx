import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../lib/icons';

/**
 * Confetti in the colours of real party confetti, as asked for: a celebration
 * is the one place the product steps outside its green. Each piece has a front
 * and a back so it shades as it tumbles; pieces are small and plentiful.
 */
const CONFETTI_PALETTE = [
  { front: '#e63946', back: '#a4161a' }, // red
  { front: '#ffd23f', back: '#e0a800' }, // yellow
  { front: '#3a86ff', back: '#1d4ed8' }, // blue
  { front: '#06d6a0', back: '#059669' }, // green
  { front: '#ff5d8f', back: '#db2777' }, // pink
  { front: '#8338ec', back: '#5b21b6' }, // purple
  { front: '#fb8500', back: '#c2410c' }, // orange
  { front: '#4cc9f0', back: '#0891b2' }, // sky
  { front: '#ffffff', back: '#e5e7eb' }, // white
];

export default function AdmissionCelebrationModal({
  isOpen,
  onClose,
  letter,
  application,
}) {
  const canvasRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isOpen) return undefined;

    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const onResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', onResize);

    // Create realistic paper confetti particles
    const count = Math.min(420, Math.max(280, Math.floor(width / 2.5)));
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    const createParticle = (spawnAnywhere = false) => {
      const typeRand = Math.random();
      const type = typeRand < 0.55 ? 'flake' : typeRand < 0.85 ? 'ribbon' : 'circle';
      const palette = CONFETTI_PALETTE[Math.floor(Math.random() * CONFETTI_PALETTE.length)];

      let w = 10;
      let h = 14;
      if (type === 'flake') {
        w = Math.random() * 3 + 5; // 5 - 8px
        h = Math.random() * 4 + 6; // 6 - 10px
      } else if (type === 'ribbon') {
        w = Math.random() * 1.5 + 2.5; // 2.5 - 4px
        h = Math.random() * 8 + 10; // 10 - 18px
      } else {
        w = Math.random() * 2.5 + 4;
        h = w;
      }

      return {
        type,
        palette,
        x: Math.random() * width,
        y: spawnAnywhere ? Math.random() * height * 1.4 - height * 0.4 : -30 - Math.random() * 60,
        w,
        h,
        vx: (Math.random() - 0.5) * 1.8,
        vy: type === 'ribbon' ? Math.random() * 2.2 + 3.2 : Math.random() * 2.5 + 2.2,
        rotation: Math.random() * Math.PI * 2,
        rotSpeed: (Math.random() - 0.5) * 0.08,
        tilt: Math.random() * Math.PI * 2,
        tiltSpeed: Math.random() * 0.08 + 0.04,
        wobble: Math.random() * Math.PI * 2,
        wobbleSpeed: Math.random() * 0.06 + 0.03,
        wobbleAmp: Math.random() * 1.5 + 0.8,
      };
    };

    // Pre-populate particles so confetti is already cascading on screen
    const particles = Array.from({ length: count }, () => createParticle(true));

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        p.tilt += p.tiltSpeed;
        p.rotation += p.rotSpeed;
        p.wobble += p.wobbleSpeed;
        p.x += Math.sin(p.wobble) * p.wobbleAmp + p.vx;
        p.y += p.vy;

        // When confetti reaches bottom, reset continuously to the top
        if (p.y > height + 30) {
          p.y = -25 - Math.random() * 40;
          p.x = Math.random() * width;
          p.vx = (Math.random() - 0.5) * 1.8;
          p.vy = p.type === 'ribbon' ? Math.random() * 2.2 + 3.2 : Math.random() * 2.5 + 2.2;
        }

        const cosTilt = Math.cos(p.tilt);
        const isFront = cosTilt > 0;
        const color = isFront ? p.palette.front : p.palette.back;

        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation);
        ctx.scale(cosTilt, 1);

        ctx.fillStyle = color;

        if (p.type === 'circle') {
          ctx.beginPath();
          ctx.arc(0, 0, p.w / 2, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        }

        ctx.restore();
      }

      // With reduced motion the confetti is drawn once and stays still.
      if (!reducedMotion) animFrameIdRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', onResize);
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
    };
  }, [isOpen]);

  if (!isOpen || !letter) return null;

  const markSeen = () => {
    try {
      localStorage.setItem(`gabstep_admission_celebration_seen_${letter.id}`, 'true');
    } catch {
      // storage can be unavailable in a private window
    }
  };

  const later = () => {
    markSeen();
    onClose?.();
  };

  const handleOpenLetter = () => {
    markSeen();
    onClose?.();
    navigate('/portal/letters');
  };

  const firstName = (application?.full_name || '').split(' ')[0];
  const school = application?.institution?.name;
  const course = application?.programs?.[0]?.name || application?.custom_course_name;

  return (
    <div
      className="admission-celebration-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="celebration-title"
      onKeyDown={(event) => {
        if (event.key === 'Escape') later();
      }}
    >
      <canvas ref={canvasRef} className="admission-confetti-canvas" aria-hidden="true" />

      <div className="celebration-card">
        <button type="button" className="celebration-close" onClick={later} aria-label="Close">
          <Icon name="close" size={18} />
        </button>

        <span className="celebration-seal" aria-hidden="true">
          <Icon name="cap" size={34} strokeWidth={1.8} />
        </span>

        <span className="celebration-eyebrow">Offer of admission</span>
        <h2 id="celebration-title">Congratulations{firstName ? `, ${firstName}` : ''}</h2>
        <p className="celebration-text">
          {school ? <strong>{school}</strong> : 'The university'} has offered you a place
          {course ? (
            <>
              {' '}on <strong>{course}</strong>
            </>
          ) : null}
          . Your {letter.title ? letter.title.toLowerCase() : 'letter'} is ready.
        </p>

        <div className="celebration-actions">
          <button type="button" className="gx-btn gx-btn-primary gx-btn-lg" onClick={handleOpenLetter} autoFocus>
            <Icon name="mail" size={18} />
            View your letter
          </button>
          <button type="button" className="gx-btn gx-btn-ghost" onClick={later}>
            Later
          </button>
        </div>
      </div>
    </div>
  );
}
