"""English offline story templates (mirrors the Indonesian pools)."""

from __future__ import annotations

EN_HORROR = {
    "hook": [
        "Everyone in that town knew one rule: never go outside after dark.",
        "There is a reason that house sat empty for so many years.",
        "He never believed in ghosts. That was before the third night.",
        "If you ever hear that sound outside your window, do not answer it.",
    ],
    "setup": [
        "The village was quiet, the kind of quiet that feels deliberate, and Marcus had just moved into the house at the end of the road.",
        "It started with the box he found in the attic, covered in dust yet somehow still warm to the touch.",
        "The neighbors only smiled when he asked about the previous owner, as if the truth was too heavy to say out loud.",
    ],
    "build": [
        "That night, the knocking came from the kitchen, slow and patient, and he stood frozen hoping it was only the wind.",
        "Every evening at the same hour, the light in the back room turned on by itself. No switch in the house was wired to it.",
        "The mirror in the hallway began showing things that were not in the room, so he covered it, and every morning the cloth was on the floor.",
        "Then the voice started saying his name, softly, like a prayer spoken backwards.",
    ],
    "climax": [
        "When he finally forced the door open, there was only darkness that moved, and from inside it, a pale hand reached out.",
        "The box held something that should have stayed buried, and the moment he opened it, every photo on the wall turned to face him.",
        "He ran outside and looked back once. In the window stood someone with his exact face, smiling.",
    ],
    "resolution": [
        "He left the next morning and never returned, but on quiet nights the neighbors still hear that sound from the empty house.",
        "They found the box on his doorstep, clean, as if someone had just wiped it. Nobody dared to touch it.",
        "To this day nobody knows what happened that night. He only ever said one thing about it: when something calls your name, it always gets an answer.",
    ],
}

EN_MOTIVATION = {
    "hook": [
        "There are two kinds of people in the world: those who quit and those that Emma called 'the lucky ones'.",
        "This is the story of someone ordinary who changed everything in three years.",
        "I met him on an ordinary afternoon. Nothing about him stood out, but his story will make you reconsider your excuses.",
    ],
    "setup": [
        "He was twenty-five when he lost everything: the job, the savings, and the belief that he was going anywhere.",
        "Every morning he walked the same streets asking for work. Thirteen rejections, and he was still counting.",
        "People around town started whispering that he dreamed too big for a man with empty hands.",
    ],
    "build": [
        "One night he wrote a single goal on a worn piece of paper and pinned it to the wall, a goal that sounded impossible to everyone else.",
        "He began waking two hours earlier, studying while the city slept, and saving the small change that used to vanish without trace.",
        "Every failure went into the notebook, followed by one line written underneath: not finished yet.",
    ],
    "climax": [
        "When the opportunity finally arrived, his hands were shaking, not from fear of failing but because he knew this was a door he had built himself, one day at a time.",
        "There was no applause and no confetti, only his grip tightening on the table and one quiet sentence: I have been preparing for this moment for years.",
    ],
    "resolution": [
        "Today that piece of paper still hangs on his wall, the goal nearly faded, with hundreds of 'not finished yet' lines beneath it.",
        "The lesson was never about luck. It was about being willing to pay the daily price while everyone else chose to stop today.",
        "He often says opportunity is never lost, it simply waits at the end of a road most people stop walking.",
    ],
}

EN_EDUCATION = {
    "hook": [
        "This fact might change how you see something you look at every single day.",
        "Few people know that behind an ordinary object lies a history that is hard to believe.",
        "Have you ever wondered why it works that way? The answer is stranger than the question.",
    ],
    "setup": [
        "It all began centuries ago, long before electricity, internet, or anything we now consider normal.",
        "The researchers of that era had no advanced tools, only curiosity and the courage to ask forbidden questions.",
        "At first the discovery was dismissed as trivial, even by the leading experts of the time.",
    ],
    "build": [
        "What makes it fascinating is that the results were the exact opposite of what everyone expected.",
        "The deeper they dug, the more new questions appeared, and each answer carried an unintended consequence.",
        "One simple experiment ended up rewriting humanity's understanding of the world.",
    ],
    "climax": [
        "Here is the most surprising part: what we call modern was already understood long ago, only described in a different language.",
        "And its impact did not stay inside the laboratory, it quietly slipped into everyday life without anyone noticing.",
    ],
    "resolution": [
        "So the next time you see it, remember the long strange history hidden behind it.",
        "This is rarely taught in school, yet its effect reaches you every single day.",
        "That is why asking 'why' always pays off, sometimes the answer is stranger than the question itself.",
    ],
}

EN_DRAMA = {
    "hook": [
        "There are meetings that change everything and meetings that break everything. This is the story of both.",
        "The letter arrived on an ordinary afternoon, with no sender and no return address.",
        "They had been friends since childhood, or at least that is what they had always believed.",
    ],
    "setup": [
        "They grew up in the same town, sharing secrets, dreams, and a promise that was never written down.",
        "By unspoken agreement they met at the same place every year, until one year he simply did not come.",
        "Everything shifted when she found that object in the old drawer, beside something that made her question every memory they shared.",
    ],
    "build": [
        "She read each letter again and again, and every line felt like a question she had never been brave enough to ask.",
        "She traced his footsteps back to the places they knew, asking the people who remembered them, and every answer made it worse.",
        "The secret that surfaced was not a grand betrayal, it was the small words that were never said in time.",
    ],
    "climax": [
        "They finally stood face to face in the same spot, but this time the person in front of her had been carrying that weight for years.",
        "When the truth finally came out there was no shouting, only a long silence and tears falling to the ground.",
    ],
    "resolution": [
        "They walked away as different people, each carrying a fragment of a story that would never be whole again.",
        "The object still sits in her drawer, proof that sometimes the most painful things could have been prevented by one small honesty.",
        "And every year she still goes back to that place, not waiting, just remembering.",
    ],
}

EN_POOL = {
    "horror": EN_HORROR,
    "motivation": EN_MOTIVATION,
    "education": EN_EDUCATION,
    "drama": EN_DRAMA,
}

__all__ = ["EN_POOL"]
