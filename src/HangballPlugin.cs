using BepInEx;
using HarmonyLib;
using UnityEngine;

namespace HangballMkII
{
    // Carries the Hangball Mk.II bundle (embedded .nobp, loaded by Blueprinter) plus the runtime patches. Only affects missiles that carry a Parachute
    // child and use OpticalSeeker (the Hangball); stock weapons are untouched.
    [BepInPlugin("nick.nuclearoption.hangballmkii", "Hangball Mk.II", "0.5.4")]
    [BepInDependency("com.nikkorap.blueprinter", BepInDependency.DependencyFlags.SoftDependency)]
    public class Plugin : BaseUnityPlugin
    {
        // Missile centre height above ground (m) that counts as touchdown. Hangball is ~1.7 m long and hangs nose-down.
        internal const float TouchdownAltitude = 1.5f;

        // With a target selected, the missile flies this far above the target and opens the chute once it passes over it.
        internal const float OverflyHeight = 1000f;

        // Under the chute the lines attach at the rear of the pack, close to the balance point, so gravity alone barely
        // rights the missile. These pull the nose straight down and damp the swing so it settles in a couple of seconds.
        internal const float HangAlignAccel = 8f;   // rad/s^2 of correction per unit of sin(tilt from vertical)
        internal const float HangDamping = 5f;      // 1/s, opposes any rotation (swing and spin)

        private void Awake()
        {
            new Harmony("nick.nuclearoption.hangballmkii").PatchAll(typeof(Plugin).Assembly);
            Logger.LogInfo("Hangball Mk.II patches applied");
        }

        internal static Parachute FindChute(Missile missile)
        {
            return missile == null ? null : missile.GetComponentInChildren<Parachute>(true);
        }
    }

    // The HF wire antennas are the missile's folding fins. Stock code unfolds them right after launch;
    // hold them stowed until the chute is open (SeekPatch unfolds them then).
    [HarmonyPatch(typeof(Missile), nameof(Missile.DeployFins))]
    internal static class DeployFinsPatch
    {
        private static bool Prefix(Missile __instance)
        {
            Parachute chute = Plugin.FindChute(__instance);
            return chute == null || chute.IsOpen();
        }
    }

    // Where the stock seeker would self-destruct at the end of its flight, deploy the chute instead.
    // Once the chute is open, skip the stock end-of-flight checks entirely.
    [HarmonyPatch(typeof(OpticalSeeker), "SlowChecks")]
    internal static class SlowChecksPatch
    {
        private static readonly AccessTools.FieldRef<MissileSeeker, Missile> MissileRef =
            AccessTools.FieldRefAccess<MissileSeeker, Missile>("missile");
        private static readonly AccessTools.FieldRef<OpticalSeeker, float> SelfDestructSpeedRef =
            AccessTools.FieldRefAccess<OpticalSeeker, float>("selfDestructAtSpeed");

        private static bool Prefix(OpticalSeeker __instance)
        {
            Missile missile = MissileRef(__instance);
            if (missile == null || missile.disabled)
                return true;

            Parachute chute = Plugin.FindChute(missile);
            if (chute == null)
                return true;

            if (chute.IsOpen())
                return false;

            bool wouldSelfDestruct = !missile.EngineOn() && missile.timeSinceSpawn > 1f &&
                (missile.LosingGround() || missile.MissedTarget() ||
                 (missile.speed < SelfDestructSpeedRef(__instance) && missile.timeSinceSpawn > 5f));
            if (!wouldSelfDestruct)
                return true;

            chute.DeployChute();
            return false;
        }
    }

    // Runs every physics step on the host in place of / after the stock guidance.
    // Before the chute opens: with a target selected, steer to a point above it and open the chute after passing over it.
    // After the chute opens: the stock seeker is skipped entirely. It would keep re-checking line of sight to the target
    // while the missile swings, dropping and re-acquiring it and steering the fins toward it, which kept the missile
    // flopping under the chute. Instead the missile just hangs, and self-destructs on reaching the ground.
    [HarmonyPatch(typeof(OpticalSeeker), nameof(OpticalSeeker.Seek))]
    internal static class SeekPatch
    {
        private static readonly AccessTools.FieldRef<MissileSeeker, Missile> MissileRef =
            AccessTools.FieldRefAccess<MissileSeeker, Missile>("missile");
        private static readonly AccessTools.FieldRef<MissileSeeker, Unit> TargetRef =
            AccessTools.FieldRefAccess<MissileSeeker, Unit>("targetUnit");
        private static readonly AccessTools.FieldRef<OpticalSeeker, GlobalPosition> KnownPosRef =
            AccessTools.FieldRefAccess<OpticalSeeker, GlobalPosition>("knownPos");
        private static readonly AccessTools.FieldRef<OpticalSeeker, Vector3> KnownVelRef =
            AccessTools.FieldRefAccess<OpticalSeeker, Vector3>("knownVel");

        private static bool Prefix(OpticalSeeker __instance)
        {
            Missile missile = MissileRef(__instance);
            if (missile == null || missile.disabled)
                return true;

            Parachute chute = Plugin.FindChute(missile);
            if (chute == null || !chute.IsOpen())
                return true;

            if (AntennasOut.Add(missile.GetInstanceID()))
                missile.DeployFins();

            HangVertical(missile.rb);

            missile.CheckRadarAlt();
            if (missile.radarAlt < Plugin.TouchdownAltitude || missile.speed < 0.5f)
            {
                missile.Arm();
                missile.Detonate(Vector3.up, hitArmor: false, hitTerrain: true);
            }
            return false;
        }

        private static void Postfix(OpticalSeeker __instance)
        {
            Missile missile = MissileRef(__instance);
            if (missile == null || missile.disabled)
                return;

            Parachute chute = Plugin.FindChute(missile);
            if (chute == null || chute.IsOpen())
                return;

            if (TargetRef(__instance) != null)
                FlyOverTarget(__instance, missile, chute);
        }

        // Missiles whose antennas have already been told to unfold (instance IDs are unique per object).
        private static readonly System.Collections.Generic.HashSet<int> AntennasOut = new System.Collections.Generic.HashSet<int>();

        private static void HangVertical(Rigidbody rb)
        {
            if (rb == null)
                return;
            Vector3 tilt = Vector3.Cross(rb.transform.forward, Vector3.down);
            rb.AddTorque(tilt * Plugin.HangAlignAccel - rb.angularVelocity * Plugin.HangDamping, ForceMode.Acceleration);
        }

        private static void FlyOverTarget(OpticalSeeker seeker, Missile missile, Parachute chute)
        {
            GlobalPosition targetPos = KnownPosRef(seeker);
            Vector3 toTarget = targetPos - missile.GlobalPosition();
            toTarget.y = 0f;
            Vector3 groundVelocity = missile.rb.velocity;
            groundVelocity.y = 0f;

            // Passed over the target: it is now behind the missile (or almost directly below it).
            bool overflown = missile.timeSinceSpawn > 3f &&
                (Vector3.Dot(toTarget, groundVelocity) < 0f || toTarget.magnitude < 50f);
            if (overflown)
            {
                chute.DeployChute();
                return;
            }

            missile.SetAimpoint(targetPos + Vector3.up * Plugin.OverflyHeight, KnownVelRef(seeker));
        }
    }

    // Under the chute the fins must not steer: zero the autopilot's control inputs so only the hang torque acts.
    [HarmonyPatch(typeof(Missile), "Steering")]
    internal static class SteeringPatch
    {
        private static readonly AccessTools.FieldRef<Missile, Vector3> InputsRef =
            AccessTools.FieldRefAccess<Missile, Vector3>("inputs");

        private static void Postfix(Missile __instance)
        {
            Parachute chute = Plugin.FindChute(__instance);
            if (chute != null && chute.IsOpen())
                InputsRef(__instance) = Vector3.zero;
        }
    }
}
