import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../lib/icons';

/**
 * Confetti in the brand's own colours.
 *
 * This was a ten-colour party palette: gold, blue, indigo, magenta, ruby,
 * violet. Nothing else in the product uses any of them, so the one moment
 * meant to feel like an achievement was also the one moment that looked like
 * another company's. The greens are the chart ramp and the accent, the cream is
 * the page, and white and the mint tint carry the sparkle, so it still reads as
 * celebration without borrowing a palette.
 *
 * Each piece has a front and a back so it shades as it tumbles.
 */
const CONFETTI_PALETTE = [
  { front: '#0b5c43', back: '#04231b' }, // brand accent
  { front: '#227152', back: '#0b5c43' }, // ramp 3
  { front: '#4e9f79', back: '#227152' }, // ramp 2
  { front: '#7fbe9c', back: '#4e9f79' }, // ramp 1
  { front: '#e1f6dd', back: '#cfebc9' }, // accent tint
  { front: '#ffffff', back: '#e6dfd1' }, // paper on the hairline
  { front: '#fbf7ef', back: '#d3c9b6' }, // page cream
];

export default function AdmissionCelebrationModal({
  isOpen,
  onClose,
  letter,
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
    const count = Math.min(180, Math.max(100, Math.floor(width / 7)));

    const createParticle = (spawnAnywhere = false) => {
      const typeRand = Math.random();
      const type = typeRand < 0.55 ? 'flake' : typeRand < 0.85 ? 'ribbon' : 'circle';
      const palette = CONFETTI_PALETTE[Math.floor(Math.random() * CONFETTI_PALETTE.length)];

      let w = 10;
      let h = 14;
      if (type === 'flake') {
        w = Math.random() * 6 + 8; // 8 - 14px
        h = Math.random() * 8 + 10; // 10 - 18px
      } else if (type === 'ribbon') {
        w = Math.random() * 2 + 4; // 4 - 6px
        h = Math.random() * 16 + 22; // 22 - 38px
      } else {
        w = Math.random() * 4 + 7;
        h = w;
      }

      return {
        type,
        palette,
        x: Math.random() * width,
        y: spawnAnywhere ? Math.random() * height - height : -30 - Math.random() * 60,
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

      animFrameIdRef.current = requestAnimationFrame(render);
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

  const handleOpenLetter = () => {
    // Record acknowledgment in localStorage so user has seen this letter
    try {
      localStorage.setItem(`gabstep_admission_celebration_seen_${letter.id}`, 'true');
    } catch {
      // localStorage may fail in private mode
    }

    if (onClose) onClose();

    // Navigate to the letters dossier
    navigate('/portal/letters');
  };

  return (
    <div className="admission-celebration-overlay" role="dialog" aria-modal="true">
      {/* ── Continuous Real Confetti Canvas Pouring from the Top ── */}
      <canvas
        ref={canvasRef}
        className="admission-confetti-canvas"
        aria-hidden="true"
      />

      {/* ── Bottom Floating Beautiful Call to Action ── */}
      <div className="admission-celebration-bottom-bar">
        <div className="admission-celebration-tag">
          CONGRATULATION, YOU HAVE BEEN OFFERED ADMISSION.
        </div>

        <button
          type="button"
          className="admission-open-letter-btn"
          onClick={handleOpenLetter}
          autoFocus
        >
          <Icon name="mail" size={20} />
          <span>Open admission letter</span>
          <span className="celebration-btn-arrow">&rarr;</span>
        </button>
      </div>
    </div>
  );
}
