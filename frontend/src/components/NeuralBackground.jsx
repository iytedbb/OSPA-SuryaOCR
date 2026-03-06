import React, { useRef, useEffect } from 'react';

const NeuralBackground = () => {
    const canvasRef = useRef(null);
    const animationRef = useRef(null);
    const nodesRef = useRef([]);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const dpr = Math.min(window.devicePixelRatio, 2);

        const resize = () => {
            canvas.width = window.innerWidth * dpr;
            canvas.height = window.innerHeight * dpr;
            canvas.style.width = window.innerWidth + 'px';
            canvas.style.height = window.innerHeight + 'px';
            ctx.scale(dpr, dpr);
        };

        resize();

        // Initialize nodes
        const nodeCount = 25;
        nodesRef.current = Array.from({ length: nodeCount }, () => ({
            x: Math.random() * window.innerWidth,
            y: Math.random() * window.innerHeight,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            radius: 3 + Math.random() * 2,
            phase: Math.random() * Math.PI * 2,
        }));

        const animate = () => {
            ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

            const time = Date.now() * 0.001;

            // Draw connections
            ctx.strokeStyle = 'rgba(185, 54, 50, 0.08)';
            ctx.lineWidth = 1;

            nodesRef.current.forEach((nodeA, i) => {
                nodesRef.current.slice(i + 1).forEach((nodeB) => {
                    const dx = nodeA.x - nodeB.x;
                    const dy = nodeA.y - nodeB.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < 180) {
                        const alpha = (1 - distance / 180) * 0.2;
                        ctx.strokeStyle = `rgba(185, 54, 50, ${alpha})`;
                        ctx.beginPath();
                        ctx.moveTo(nodeA.x, nodeA.y);
                        ctx.lineTo(nodeB.x, nodeB.y);
                        ctx.stroke();
                    }
                });
            });

            // Update and draw nodes
            nodesRef.current.forEach((node) => {
                // Update position
                node.x += node.vx;
                node.y += node.vy;

                // Bounce off edges
                if (node.x < 0 || node.x > window.innerWidth) node.vx *= -1;
                if (node.y < 0 || node.y > window.innerHeight) node.vy *= -1;

                // Draw node
                const scale = 1 + Math.sin(time * 2 + node.phase) * 0.3;
                const alpha = 0.4 + Math.sin(time + node.phase) * 0.2;

                ctx.fillStyle = `rgba(185, 54, 50, ${alpha})`;
                ctx.beginPath();
                ctx.arc(node.x, node.y, node.radius * scale, 0, Math.PI * 2);
                ctx.fill();

                // Glow effect
                ctx.shadowBlur = 15;
                ctx.shadowColor = 'rgba(185, 54, 50, 0.3)';
                ctx.fill();
                ctx.shadowBlur = 0;
            });

            animationRef.current = requestAnimationFrame(animate);
        };

        animate();

        const handleResize = () => {
            resize();
        };

        window.addEventListener('resize', handleResize);

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            window.removeEventListener('resize', handleResize);
        };
    }, []);

    return (
        <canvas
            ref={canvasRef}
            id="neural-canvas"
            className="fixed inset-0 w-full h-full pointer-events-none z-0 opacity-25 mix-blend-multiply"
        />
    );
};

export default NeuralBackground;
