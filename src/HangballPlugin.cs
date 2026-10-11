using BepInEx;
using HarmonyLib;
using UnityEngine;

namespace HangballMkII
{
    // Carries the Hangball Mk.II bundle (embedded .nobp, loaded by Blueprinter) plus the runtime patches. Only affects missiles that carry a Parachute
    // child and use OpticalSeeker (the Hangball); stock weapons are untouched.
    [BepInPlugin("nick.nuclearoption.hangballmkii", "Hangball Mk.II", "1.0.0")]
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

        // Fraction of the spin about the vertical removed every physics step under the chute. The stock chute pulls the
        // belly toward the lines (it is written for bombs that hang level), which makes a nose-down missile keep yawing.
        internal const float HangSpinKill = 0.8f;

        // The chute opens once the missile has flown this far (m), with or without a target.
        internal const float ChuteDeployDistance = 15000f;

        private void Awake()
        {
            var harmony = new Harmony("nick.nuclearoption.hangballmkii");
            harmony.PatchAll(typeof(Plugin).Assembly);
            ChuteVisuals.Patch(harmony, Logger);
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
    // Before the chute opens: open it after 15 km of flight, or right away if the target is lost. With a target selected,
    // steer to a point above it and open the chute after passing over it.
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

            int id = missile.GetInstanceID();
            DistanceFlown.TryGetValue(id, out float flown);
            flown += missile.speed * Time.fixedDeltaTime;
            DistanceFlown[id] = flown;
            if (flown >= Plugin.ChuteDeployDistance)
            {
                chute.DeployChute();
                return;
            }

            Unit target = TargetRef(__instance);
            if (target != null && !target.disabled)
            {
                HadTarget.Add(id);
                FlyOverTarget(__instance, missile, chute);
            }
            else if (HadTarget.Contains(id))
            {
                // The target was lost (destroyed or removed): open the chute right away.
                chute.DeployChute();
            }
        }

        // Distance flown so far and missiles that have had a target, per missile (instance IDs are unique per object).
        private static readonly System.Collections.Generic.Dictionary<int, float> DistanceFlown =
            new System.Collections.Generic.Dictionary<int, float>();
        private static readonly System.Collections.Generic.HashSet<int> HadTarget = new System.Collections.Generic.HashSet<int>();

        // Missiles whose antennas have already been told to unfold (instance IDs are unique per object).
        private static readonly System.Collections.Generic.HashSet<int> AntennasOut = new System.Collections.Generic.HashSet<int>();

        private static void HangVertical(Rigidbody rb)
        {
            if (rb == null)
                return;
            Vector3 spin = rb.angularVelocity;
            spin.y *= 1f - Plugin.HangSpinKill;
            rb.angularVelocity = spin;
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

    // The stock chute aims the canopy and lines using the missile's nose as the "up" hint. Hanging nose-down that hint is
    // parallel to the lines, so the canopy and lines spin visually. Re-aim them using a fixed world direction instead.
    internal static class ChuteVisuals
    {
        private static System.Reflection.FieldInfo canopyField;
        private static System.Reflection.FieldInfo linesField;

        internal static void Patch(Harmony harmony, BepInEx.Logging.ManualLogSource log)
        {
            canopyField = AccessTools.Field(typeof(Parachute), "canopy");
            linesField = AccessTools.Field(typeof(Parachute), "lines");
            if (canopyField == null || linesField == null)
            {
                log.LogWarning("Parachute canopy/lines fields not found; chute visuals left stock");
                return;
            }
            var postfix = new HarmonyMethod(typeof(ChuteVisuals), nameof(Postfix));
            foreach (string name in new[] { "FixedUpdate", "Update", "LateUpdate" })
            {
                var method = AccessTools.DeclaredMethod(typeof(Parachute), name);
                if (method != null)
                    harmony.Patch(method, postfix: postfix);
            }
        }

        private static Transform AsTransform(object value)
        {
            if (value is Component component)
                return component.transform;
            return (value as GameObject)?.transform;
        }

        private static void Postfix(Parachute __instance)
        {
            if (__instance == null || __instance.GetComponentInParent<Missile>() == null)
                return;
            Transform canopy = AsTransform(canopyField.GetValue(__instance));
            Transform lines = AsTransform(linesField.GetValue(__instance));
            if (canopy != null)
                canopy.LookAt(__instance.transform.position, Vector3.forward);
            if (canopy != null && lines != null)
                lines.LookAt(canopy.position, Vector3.forward);
        }
    }
}
